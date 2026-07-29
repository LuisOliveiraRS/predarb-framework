from __future__ import annotations

import asyncio
from copy import deepcopy
from math import isclose
from typing import Any, Mapping
from uuid import uuid4

from app.paper.shadow_execution_models import (
    PROTECTED_FALSE_FLAGS,
    SHADOW_SAFETY_FLAGS,
    ShadowExecutionRecord,
    ShadowFill,
    ShadowMarketReference,
    ShadowOrderIntent,
)
from app.paper.shadow_execution_repository import (
    ShadowExecutionAuditRepository,
    shadow_execution_audit_repository,
)
from app.real_markets.economics import (
    EconomicOpportunityEngine,
    economic_opportunity_engine,
)
from app.real_markets.models import (
    MarketSnapshot,
)
from app.real_markets.service import (
    RealMarketDataService,
    real_market_data_service,
)


class ShadowExecutionSimulator:
    """
    Converte avaliacao economica somente leitura em uma simulacao Shadow.

    Este componente nao importa exchanges, adapters, OMS, wallets
    ou qualquer mecanismo de envio de ordens.
    """

    PARITY_ABSOLUTE_TOLERANCE = 0.000001

    def __init__(
        self,
        *,
        economic_engine: EconomicOpportunityEngine = (
            economic_opportunity_engine
        ),
        market_data_service: RealMarketDataService = (
            real_market_data_service
        ),
        audit_repository: ShadowExecutionAuditRepository = (
            shadow_execution_audit_repository
        ),
    ) -> None:
        self.economic_engine = economic_engine
        self.market_data_service = market_data_service
        self.audit_repository = audit_repository

        self.simulation_count = 0
        self.persisted_count = 0
        self.rejected_count = 0
        self.last_execution_id: str | None = None
        self.last_error: str | None = None

    @staticmethod
    def _text(
        value: Any,
        default: str = "",
    ) -> str:
        return str(
            default if value is None else value
        ).strip()

    @staticmethod
    def _float(
        value: Any,
        field_name: str,
        *,
        minimum: float | None = None,
    ) -> float:
        if isinstance(value, bool):
            raise TypeError(
                f"{field_name} nao pode ser booleano."
            )

        try:
            resolved = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"{field_name} deve ser numerico."
            ) from exc

        if (
            minimum is not None
            and resolved < minimum
        ):
            raise ValueError(
                f"{field_name} deve ser maior ou igual a {minimum}."
            )

        return resolved

    @staticmethod
    def _split_market_key(
        key: str,
    ) -> tuple[str, str]:
        normalized = str(
            key or ""
        ).strip()

        connector_id, separator, market_id = (
            normalized.partition(":")
        )

        if (
            not separator
            or not connector_id.strip()
            or not market_id.strip()
        ):
            raise ValueError(
                f"Chave de mercado invalida: {key!r}"
            )

        return (
            connector_id.strip(),
            market_id.strip(),
        )

    @staticmethod
    def _validate_evaluation_safety(
        evaluation: Mapping[str, Any],
    ) -> None:
        for flag in PROTECTED_FALSE_FLAGS:
            if (
                flag in evaluation
                and evaluation[flag] is not False
            ):
                raise ValueError(
                    f"A avaliacao economica ativou "
                    f"a flag protegida {flag!r}."
                )

        for flag in (
            "order_submission_available",
            "automatic_execution_authorized",
        ):
            if evaluation.get(flag) is True:
                raise ValueError(
                    f"A avaliacao economica nao e segura: "
                    f"{flag}=True."
                )

    @staticmethod
    def _find_snapshot(
        snapshots: Mapping[str, MarketSnapshot],
        *,
        connector_id: str,
        market_id: str,
    ) -> MarketSnapshot:
        key = (
            f"{connector_id}:"
            f"{market_id}"
        )

        snapshot = snapshots.get(key)

        if snapshot is None:
            raise ValueError(
                "Snapshot ausente para a perna "
                f"economica: {key}"
            )

        return snapshot

    @staticmethod
    def _rejection_record(
        evaluation: Mapping[str, Any],
        reasons: list[str],
    ) -> ShadowExecutionRecord:
        normalized_reasons = tuple(
            str(item).strip()
            for item in reasons
            if str(item).strip()
        )

        if not normalized_reasons:
            normalized_reasons = (
                "SHADOW_SIMULATION_REJECTED",
            )

        return ShadowExecutionRecord(
            opportunity_id=str(
                evaluation.get("match_id")
                or ""
            ),
            status="REJECTED",
            rejection_reasons=(
                normalized_reasons
            ),
            metadata={
                "source": (
                    "EconomicOpportunityEngine"
                ),
                "economic_status": (
                    evaluation.get("status")
                ),
                "left_key": (
                    evaluation.get("left_key")
                ),
                "right_key": (
                    evaluation.get("right_key")
                ),
                "economic_evaluation": deepcopy(
                    dict(evaluation)
                ),
                "financial_execution": False,
                "live_execution": False,
            },
        )

    def build_record(
        self,
        *,
        evaluation: Mapping[str, Any],
        snapshots: Mapping[
            str,
            MarketSnapshot,
        ],
    ) -> ShadowExecutionRecord:
        if not isinstance(
            evaluation,
            Mapping,
        ):
            raise TypeError(
                "evaluation deve ser um mapeamento."
            )

        if not isinstance(
            snapshots,
            Mapping,
        ):
            raise TypeError(
                "snapshots deve ser um mapeamento."
            )

        self._validate_evaluation_safety(
            evaluation
        )

        if (
            evaluation.get(
                "manual_match_confirmed"
            )
            is not True
        ):
            return self._rejection_record(
                evaluation,
                [
                    "MANUAL_MATCH_NOT_CONFIRMED",
                ],
            )

        economic_status = self._text(
            evaluation.get("status")
        ).upper()

        if economic_status != "PROFITABLE":
            reasons = list(
                evaluation.get(
                    "reason_codes"
                )
                or []
            )

            if not reasons:
                reasons.append(
                    "ECONOMIC_STATUS_NOT_PROFITABLE"
                )

            return self._rejection_record(
                evaluation,
                reasons,
            )

        direction = evaluation.get(
            "best_direction"
        )

        if not isinstance(
            direction,
            Mapping,
        ):
            return self._rejection_record(
                evaluation,
                [
                    "BEST_DIRECTION_MISSING",
                ],
            )

        if (
            self._text(
                direction.get("status")
            ).upper()
            != "PROFITABLE"
        ):
            return self._rejection_record(
                evaluation,
                list(
                    direction.get(
                        "reason_codes"
                    )
                    or [
                        "BEST_DIRECTION_NOT_PROFITABLE"
                    ]
                ),
            )

        legs = direction.get(
            "legs"
        )

        if (
            not isinstance(legs, list)
            or len(legs) != 2
        ):
            return self._rejection_record(
                evaluation,
                [
                    "INVALID_ECONOMIC_LEGS",
                ],
            )

        quantity = self._float(
            direction.get(
                "simulated_quantity"
            ),
            "simulated_quantity",
            minimum=0.00000001,
        )

        execution_id = str(
            uuid4()
        )

        market_references: list[
            ShadowMarketReference
        ] = []

        orders: list[
            ShadowOrderIntent
        ] = []

        fills: list[
            ShadowFill
        ] = []

        for index, raw_leg in enumerate(
            legs,
            start=1,
        ):
            if not isinstance(
                raw_leg,
                Mapping,
            ):
                raise ValueError(
                    f"Perna economica {index} invalida."
                )

            connector_id = self._text(
                raw_leg.get(
                    "connector_id"
                )
            )

            market_id = self._text(
                raw_leg.get(
                    "market_id"
                )
            )

            outcome_id = self._text(
                raw_leg.get(
                    "outcome_id"
                )
            )

            if (
                not connector_id
                or not market_id
                or not outcome_id
            ):
                raise ValueError(
                    f"Perna economica {index} incompleta."
                )

            snapshot = self._find_snapshot(
                snapshots,
                connector_id=connector_id,
                market_id=market_id,
            )

            if snapshot.market.status != "OPEN":
                raise ValueError(
                    "A simulacao Shadow exige "
                    "mercado OPEN."
                )

            reference = (
                ShadowMarketReference
                .from_snapshot(
                    snapshot,
                    outcome_id=outcome_id,
                )
            )

            ask = reference.ask

            if ask is None:
                raise ValueError(
                    "A simulacao Shadow exige ask."
                )

            ask_size = reference.ask_size

            if ask_size is None:
                raise ValueError(
                    "A simulacao Shadow exige ask_size."
                )

            if quantity > ask_size + 1e-9:
                raise ValueError(
                    "A quantidade economica excede "
                    "a liquidez do snapshot."
                )

            economic_ask = self._float(
                raw_leg.get("ask"),
                "economic_ask",
                minimum=0.0,
            )

            if not isclose(
                ask,
                economic_ask,
                rel_tol=0.0,
                abs_tol=self.PARITY_ABSOLUTE_TOLERANCE,
            ):
                raise ValueError(
                    "O ask do snapshot diverge "
                    "da avaliacao economica."
                )

            fee_rate = self._float(
                raw_leg.get(
                    "fee_rate",
                    0.0,
                ),
                "fee_rate",
                minimum=0.0,
            )

            slippage_bps = self._float(
                raw_leg.get(
                    "slippage_bps",
                    0.0,
                ),
                "slippage_bps",
                minimum=0.0,
            )

            slippage_rate = (
                slippage_bps
                / 10_000.0
            )

            raw_notional = (
                quantity
                * ask
            )

            slippage_cost = (
                raw_notional
                * slippage_rate
            )

            order_id = (
                f"shadow:{execution_id}:"
                f"leg-{index}"
            )

            order = ShadowOrderIntent(
                market=reference,
                side="BUY",
                quantity=quantity,
                requested_price=ask,
                opportunity_id=self._text(
                    evaluation.get(
                        "match_id"
                    )
                ),
                order_id=order_id,
                metadata={
                    "execution_id": (
                        execution_id
                    ),
                    "leg_index": index,
                    "canonical_outcome": (
                        raw_leg.get(
                            "canonical_outcome"
                        )
                    ),
                    "source": (
                        "EconomicOpportunityEngine"
                    ),
                    "financial_execution": False,
                    "live_execution": False,
                },
            )

            fill = ShadowFill(
                order_id=order.order_id,
                side=order.side,
                quantity=quantity,
                requested_price=ask,
                fill_price=ask,
                fee_rate=fee_rate,
                fee_basis_price=ask,
                explicit_slippage_cost=(
                    slippage_cost
                ),
                metadata={
                    "execution_id": (
                        execution_id
                    ),
                    "leg_index": index,
                    "price_source": (
                        "REAL_MARKET_SNAPSHOT_ASK"
                    ),
                    "slippage_model": (
                        "ECONOMIC_CONFIGURATION_BPS"
                    ),
                    "simulation_only": True,
                    "financial_execution": False,
                    "live_execution": False,
                },
            )

            market_references.append(
                reference
            )

            orders.append(
                order
            )

            fills.append(
                fill
            )

        expected_payout = self._float(
            direction.get(
                "simulated_payout"
            ),
            "simulated_payout",
            minimum=0.0,
        )

        record = ShadowExecutionRecord(
            opportunity_id=self._text(
                evaluation.get(
                    "match_id"
                )
            ),
            status="SIMULATED",
            market_references=tuple(
                market_references
            ),
            orders=tuple(
                orders
            ),
            fills=tuple(
                fills
            ),
            expected_payout=(
                expected_payout
            ),
            execution_id=execution_id,
            metadata={
                "source": (
                    "EconomicOpportunityEngine"
                ),
                "economic_direction": (
                    direction.get(
                        "direction"
                    )
                ),
                "economic_evaluated_at": (
                    evaluation.get(
                        "evaluated_at"
                    )
                ),
                "left_key": (
                    evaluation.get(
                        "left_key"
                    )
                ),
                "right_key": (
                    evaluation.get(
                        "right_key"
                    )
                ),
                "manual_match_confirmed": True,
                "economic_evaluation": deepcopy(
                    dict(evaluation)
                ),
                "financial_execution": False,
                "live_execution": False,
            },
        )

        economic_total_cost = (
            self._float(
                direction.get(
                    "total_cost"
                ),
                "total_cost",
                minimum=0.0,
            )
        )

        shadow_total_cost = max(
            0.0,
            -record.net_cash_flow,
        )

        if not isclose(
            shadow_total_cost,
            economic_total_cost,
            rel_tol=0.0,
            abs_tol=self.PARITY_ABSOLUTE_TOLERANCE,
        ):
            raise ValueError(
                "Falha de paridade no custo total: "
                f"economic={economic_total_cost}, "
                f"shadow={shadow_total_cost}."
            )

        economic_net_profit = (
            self._float(
                direction.get(
                    "net_profit"
                ),
                "net_profit",
            )
        )

        if not isclose(
            record.simulated_profit,
            economic_net_profit,
            rel_tol=0.0,
            abs_tol=self.PARITY_ABSOLUTE_TOLERANCE,
        ):
            raise ValueError(
                "Falha de paridade no lucro liquido: "
                f"economic={economic_net_profit}, "
                f"shadow={record.simulated_profit}."
            )

        return record

    async def simulate_evaluation(
        self,
        *,
        evaluation: Mapping[str, Any],
        force_refresh: bool = False,
        persist: bool = False,
    ) -> dict[str, Any]:
        self.last_error = None

        left_key = self._text(
            evaluation.get(
                "left_key"
            )
        )

        right_key = self._text(
            evaluation.get(
                "right_key"
            )
        )

        snapshots: dict[
            str,
            MarketSnapshot,
        ] = {}

        if left_key and right_key:
            (
                left_connector_id,
                left_market_id,
            ) = self._split_market_key(
                left_key
            )

            (
                right_connector_id,
                right_market_id,
            ) = self._split_market_key(
                right_key
            )

            left_snapshot, right_snapshot = (
                await asyncio.gather(
                    self.market_data_service.get_snapshot(
                        connector_id=(
                            left_connector_id
                        ),
                        market_id=(
                            left_market_id
                        ),
                        force_refresh=(
                            force_refresh
                        ),
                    ),
                    self.market_data_service.get_snapshot(
                        connector_id=(
                            right_connector_id
                        ),
                        market_id=(
                            right_market_id
                        ),
                        force_refresh=(
                            force_refresh
                        ),
                    ),
                )
            )

            snapshots[
                left_snapshot.key
            ] = left_snapshot

            snapshots[
                right_snapshot.key
            ] = right_snapshot

        try:
            record = self.build_record(
                evaluation=evaluation,
                snapshots=snapshots,
            )
        except Exception as exc:
            self.last_error = str(exc)
            raise

        self.simulation_count += 1
        self.last_execution_id = (
            record.execution_id
        )

        if record.status == "REJECTED":
            self.rejected_count += 1

        audit_record = None

        if persist:
            audit_record = (
                self.audit_repository.append(
                    record.to_audit_payload(),
                    event_type=(
                        "SHADOW_EXECUTION"
                        if (
                            record.status
                            == "SIMULATED"
                        )
                        else "SHADOW_REJECTION"
                    ),
                )
            )

            self.persisted_count += 1

        return {
            "status": record.status,
            "record": record.to_dict(),
            "persisted": bool(
                audit_record
            ),
            "audit": audit_record,
            **deepcopy(
                SHADOW_SAFETY_FLAGS
            ),
        }

    async def simulate_match(
        self,
        *,
        match_id: str,
        force_refresh: bool = False,
        persist: bool = False,
    ) -> dict[str, Any]:
        evaluation = (
            await self.economic_engine
            .evaluate_match(
                match_id=match_id,
                force_refresh=(
                    force_refresh
                ),
            )
        )

        return await self.simulate_evaluation(
            evaluation=evaluation,
            force_refresh=False,
            persist=persist,
        )

    def status(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "simulation_count": (
                self.simulation_count
            ),
            "persisted_count": (
                self.persisted_count
            ),
            "rejected_count": (
                self.rejected_count
            ),
            "last_execution_id": (
                self.last_execution_id
            ),
            "last_error": (
                self.last_error
            ),
            "persistence_default": False,
            "manual_match_required": True,
            "profitable_evaluation_required": True,
            "exchange_imports": False,
            "order_submission_available": False,
            **deepcopy(
                SHADOW_SAFETY_FLAGS
            ),
        }


shadow_execution_simulator = (
    ShadowExecutionSimulator()
)
