from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import Lock
from time import perf_counter
from typing import Any, Mapping
from uuid import uuid4

from app.paper.shadow_execution_models import (
    SHADOW_SAFETY_FLAGS,
)
from app.paper.shadow_execution_simulator import (
    ShadowExecutionSimulator,
    shadow_execution_simulator,
)
from app.real_markets.economics import (
    EconomicOpportunityEngine,
    economic_opportunity_engine,
)


PROTECTED_FALSE_FLAGS = (
    "paper_execution_authorized",
    "live_authorization",
    "execution_authorized",
    "live_execution",
    "financial_execution",
    "next_step_authorized",
    "order_submission_available",
    "automatic_execution_authorized",
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


class ShadowExecutionRuntime:
    """
    Runtime operacional da Fase 9F.

    Responsabilidades:
    - ler somente correspond?ncias manuais confirmadas;
    - avaliar oportunidades econ?micas;
    - selecionar somente avalia??es PROFITABLE;
    - executar simula??es Shadow isoladas;
    - impedir sobreposi??o de ciclos;
    - manter m?tricas operacionais em mem?ria.

    Este runtime n?o importa exchanges, OMS, carteira,
    credenciais ou mecanismos de envio de ordens.
    """

    def __init__(
        self,
        *,
        economic_engine: EconomicOpportunityEngine = (
            economic_opportunity_engine
        ),
        simulator: ShadowExecutionSimulator = (
            shadow_execution_simulator
        ),
        max_opportunities_per_cycle: int = 10,
        persistence_default: bool = False,
        force_refresh_default: bool = False,
    ) -> None:
        resolved_limit = int(
            max_opportunities_per_cycle
        )

        if resolved_limit <= 0:
            raise ValueError(
                "max_opportunities_per_cycle "
                "deve ser positivo."
            )

        if persistence_default is not False:
            raise ValueError(
                "A persist?ncia autom?tica do "
                "Shadow Runtime deve permanecer "
                "desabilitada por padr?o."
            )

        self.economic_engine = economic_engine
        self.simulator = simulator
        self.max_opportunities_per_cycle = (
            resolved_limit
        )
        self.persistence_default = False
        self.force_refresh_default = bool(
            force_refresh_default
        )

        self._cycle_lock = Lock()
        self._scheduler_connected = False

        self.cycle_count = 0
        self.completed_cycle_count = 0
        self.failed_cycle_count = 0
        self.skipped_cycle_count = 0

        self.evaluated_opportunity_count = 0
        self.eligible_opportunity_count = 0
        self.processed_opportunity_count = 0
        self.simulated_count = 0
        self.rejected_count = 0
        self.error_count = 0

        self.last_cycle_id: str | None = None
        self.last_started_at: str | None = None
        self.last_completed_at: str | None = None
        self.last_duration_ms: float | None = None
        self.last_error: str | None = None
        self.last_cycle: dict[str, Any] | None = None

    @staticmethod
    def _safe_flags() -> dict[str, Any]:
        flags = deepcopy(
            SHADOW_SAFETY_FLAGS
        )

        flags.update(
            {
                "automatic_execution_authorized": False,
                "order_submission_available": False,
            }
        )

        return flags

    @classmethod
    def _validate_safety_mapping(
        cls,
        payload: Mapping[str, Any],
        *,
        context: str,
    ) -> None:
        if not isinstance(
            payload,
            Mapping,
        ):
            raise TypeError(
                f"{context} deve ser um mapeamento."
            )

        unsafe = [
            flag
            for flag in PROTECTED_FALSE_FLAGS
            if (
                flag in payload
                and payload.get(flag) is not False
            )
        ]

        if unsafe:
            raise ValueError(
                f"{context} cont?m flags inseguras: "
                + ", ".join(sorted(unsafe))
            )

    @staticmethod
    def _opportunities(
        payload: Mapping[str, Any],
    ) -> list[dict[str, Any]]:
        raw = payload.get(
            "opportunities",
            [],
        )

        if not isinstance(
            raw,
            list,
        ):
            raise TypeError(
                "opportunities deve ser uma lista."
            )

        resolved: list[
            dict[str, Any]
        ] = []

        for index, item in enumerate(raw):
            if not isinstance(
                item,
                Mapping,
            ):
                raise TypeError(
                    "Oportunidade econ?mica inv?lida "
                    f"no ?ndice {index}."
                )

            resolved.append(
                deepcopy(dict(item))
            )

        return resolved

    def _runtime_snapshot(
        self,
    ) -> dict[str, Any]:
        return {
            "cycle_count": self.cycle_count,
            "completed_cycle_count": (
                self.completed_cycle_count
            ),
            "failed_cycle_count": (
                self.failed_cycle_count
            ),
            "skipped_cycle_count": (
                self.skipped_cycle_count
            ),
            "evaluated_opportunity_count": (
                self.evaluated_opportunity_count
            ),
            "eligible_opportunity_count": (
                self.eligible_opportunity_count
            ),
            "processed_opportunity_count": (
                self.processed_opportunity_count
            ),
            "simulated_count": (
                self.simulated_count
            ),
            "rejected_count": (
                self.rejected_count
            ),
            "error_count": self.error_count,
        }

    async def run_cycle(
        self,
        *,
        force_refresh: bool | None = None,
        persist: bool | None = None,
        max_opportunities: int | None = None,
    ) -> dict[str, Any]:
        resolved_force_refresh = (
            self.force_refresh_default
            if force_refresh is None
            else bool(force_refresh)
        )

        resolved_persist = (
            self.persistence_default
            if persist is None
            else bool(persist)
        )

        resolved_limit = (
            self.max_opportunities_per_cycle
            if max_opportunities is None
            else int(max_opportunities)
        )

        if resolved_limit <= 0:
            raise ValueError(
                "max_opportunities deve ser positivo."
            )

        if not self._cycle_lock.acquire(
            blocking=False
        ):
            self.skipped_cycle_count += 1

            return {
                "status": "SKIPPED_ALREADY_RUNNING",
                "cycle_id": None,
                "started_at": None,
                "completed_at": _utc_now(),
                "force_refresh": resolved_force_refresh,
                "persist_requested": resolved_persist,
                "max_opportunities": resolved_limit,
                "results": [],
                "errors": [],
                "runtime": self._runtime_snapshot(),
                **self._safe_flags(),
            }

        cycle_id = str(
            uuid4()
        )
        started_at = _utc_now()
        started_clock = perf_counter()

        self.cycle_count += 1
        self.last_cycle_id = cycle_id
        self.last_started_at = started_at
        self.last_error = None

        try:
            economic_payload = (
                await self.economic_engine
                .evaluate_confirmed_matches(
                    force_refresh=(
                        resolved_force_refresh
                    ),
                )
            )

            self._validate_safety_mapping(
                economic_payload,
                context=(
                    "Resultado econ?mico agregado"
                ),
            )

            opportunities = self._opportunities(
                economic_payload
            )

            self.evaluated_opportunity_count += len(
                opportunities
            )

            eligible = [
                item
                for item in opportunities
                if item.get("status")
                == "PROFITABLE"
            ]

            self.eligible_opportunity_count += len(
                eligible
            )

            selected = eligible[
                :resolved_limit
            ]

            results: list[
                dict[str, Any]
            ] = []

            errors: list[
                dict[str, Any]
            ] = []

            for evaluation in selected:
                try:
                    self._validate_safety_mapping(
                        evaluation,
                        context=(
                            "Avalia??o econ?mica"
                        ),
                    )

                    simulation = (
                        await self.simulator
                        .simulate_evaluation(
                            evaluation=evaluation,
                            force_refresh=False,
                            persist=resolved_persist,
                        )
                    )

                    self._validate_safety_mapping(
                        simulation,
                        context=(
                            "Resultado da simula??o"
                        ),
                    )

                    results.append(
                        deepcopy(simulation)
                    )

                    self.processed_opportunity_count += 1

                    if (
                        simulation.get("status")
                        == "SIMULATED"
                    ):
                        self.simulated_count += 1

                    elif (
                        simulation.get("status")
                        == "REJECTED"
                    ):
                        self.rejected_count += 1

                except Exception as exc:
                    self.error_count += 1

                    errors.append(
                        {
                            "match_id": (
                                evaluation.get(
                                    "match_id"
                                )
                            ),
                            "status": "ERROR",
                            "error": str(exc),
                            **self._safe_flags(),
                        }
                    )

            if errors:
                cycle_status = (
                    "COMPLETED_WITH_ERRORS"
                )

            elif not opportunities:
                cycle_status = (
                    "NO_CONFIRMED_MATCHES"
                    if (
                        economic_payload.get(
                            "status"
                        )
                        == "NO_CONFIRMED_MATCHES"
                    )
                    else "NO_OPPORTUNITIES"
                )

            elif not eligible:
                cycle_status = (
                    "NO_PROFITABLE_OPPORTUNITIES"
                )

            else:
                cycle_status = "COMPLETED"

            completed_at = _utc_now()
            duration_ms = round(
                (
                    perf_counter()
                    - started_clock
                )
                * 1000,
                3,
            )

            payload = {
                "status": cycle_status,
                "cycle_id": cycle_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "force_refresh": (
                    resolved_force_refresh
                ),
                "persist_requested": (
                    resolved_persist
                ),
                "max_opportunities": (
                    resolved_limit
                ),
                "economic_status": (
                    economic_payload.get(
                        "status"
                    )
                ),
                "confirmed_matches": int(
                    economic_payload.get(
                        "confirmed_matches",
                        0,
                    )
                    or 0
                ),
                "evaluated_opportunities": len(
                    opportunities
                ),
                "eligible_opportunities": len(
                    eligible
                ),
                "selected_opportunities": len(
                    selected
                ),
                "simulated": sum(
                    1
                    for item in results
                    if item.get("status")
                    == "SIMULATED"
                ),
                "rejected": sum(
                    1
                    for item in results
                    if item.get("status")
                    == "REJECTED"
                ),
                "errors_count": len(errors),
                "results": results,
                "errors": errors,
                "runtime": self._runtime_snapshot(),
                **self._safe_flags(),
            }

            self.completed_cycle_count += 1
            self.last_completed_at = completed_at
            self.last_duration_ms = duration_ms
            self.last_cycle = deepcopy(payload)

            return payload

        except Exception as exc:
            self.failed_cycle_count += 1
            self.error_count += 1
            self.last_error = str(exc)

            completed_at = _utc_now()
            duration_ms = round(
                (
                    perf_counter()
                    - started_clock
                )
                * 1000,
                3,
            )

            payload = {
                "status": "FAILED",
                "cycle_id": cycle_id,
                "started_at": started_at,
                "completed_at": completed_at,
                "duration_ms": duration_ms,
                "force_refresh": (
                    resolved_force_refresh
                ),
                "persist_requested": (
                    resolved_persist
                ),
                "max_opportunities": (
                    resolved_limit
                ),
                "error": str(exc),
                "results": [],
                "errors": [
                    {
                        "status": "ERROR",
                        "error": str(exc),
                        **self._safe_flags(),
                    }
                ],
                "runtime": self._runtime_snapshot(),
                **self._safe_flags(),
            }

            self.last_completed_at = completed_at
            self.last_duration_ms = duration_ms
            self.last_cycle = deepcopy(payload)

            return payload

        finally:
            self._cycle_lock.release()

    def set_scheduler_connected(
        self,
        connected: bool,
    ) -> None:
        """
        Atualiza somente o estado observacional
        da integra??o com o scheduler.

        Este m?todo n?o inicia ciclos, n?o cria
        jobs e n?o autoriza execu??o financeira.
        """

        self._scheduler_connected = bool(
            connected
        )

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "status": (
                "RUNNING"
                if self._cycle_lock.locked()
                else "READY"
            ),
            "phase": "9F",
            "runtime_mode": (
                "SHADOW_SIMULATION_ONLY"
            ),
            "manual_match_required": True,
            "profitable_evaluation_required": True,
            "persistence_default": (
                self.persistence_default
            ),
            "force_refresh_default": (
                self.force_refresh_default
            ),
            "max_opportunities_per_cycle": (
                self.max_opportunities_per_cycle
            ),
            "overlap_protection": True,
            "scheduler_connected": (
                self._scheduler_connected
            ),
            "paper_account_mutation": False,
            "exchange_imports": False,
            "oms_imports": False,
            "wallet_access": False,
            "credential_access": False,
            "last_cycle_id": (
                self.last_cycle_id
            ),
            "last_started_at": (
                self.last_started_at
            ),
            "last_completed_at": (
                self.last_completed_at
            ),
            "last_duration_ms": (
                self.last_duration_ms
            ),
            "last_error": self.last_error,
            "last_cycle": deepcopy(
                self.last_cycle
            ),
            **self._runtime_snapshot(),
            **self._safe_flags(),
        }


shadow_execution_runtime = (
    ShadowExecutionRuntime()
)
