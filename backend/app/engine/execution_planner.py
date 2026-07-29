from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.engine.execution_estimator import (
    ExecutionEstimator,
    execution_estimator,
)


class ExecutionPlanner:
    """
    Define se uma oportunidade está pronta para
    seguir à criação de ordens.

    Este componente apenas planeja. Ele não executa.
    """

    MIN_PROFIT = 1.0

    def __init__(
        self,
        *,
        estimator: ExecutionEstimator | None = None,
        min_profit: float = MIN_PROFIT,
        require_pipeline_approval: bool = False,
        require_known_slippage: bool = True,
    ) -> None:
        self.estimator = (
            estimator or execution_estimator
        )

        self.min_profit = self._non_negative_number(
            min_profit,
            "min_profit",
        )

        self.require_pipeline_approval = bool(
            require_pipeline_approval
        )

        self.require_known_slippage = bool(
            require_known_slippage
        )

        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(
        opportunities: Any,
    ) -> list[Any]:
        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            Mapping,
        ):
            return [opportunities]

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "opportunities deve ser uma coleção."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(opportunities)

        return [opportunities]

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(target, Mapping):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @staticmethod
    def _non_negative_number(
        value: Any,
        field_name: str,
    ) -> float:
        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if not isfinite(number) or number < 0:
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser finito e não negativo."
            )

        return number

    @classmethod
    def _metadata(
        cls,
        opportunity: Any,
    ) -> dict[str, Any]:
        metadata = cls._read_field(
            opportunity,
            "metadata",
            {},
        )

        if isinstance(metadata, dict):
            return metadata

        return {}

    @classmethod
    def _estimate(
        cls,
        opportunity: Any,
    ) -> dict[str, Any] | None:
        estimate = cls._read_field(
            opportunity,
            "execution_estimate",
            None,
        )

        if isinstance(estimate, Mapping):
            return dict(estimate)

        metadata_estimate = cls._metadata(
            opportunity
        ).get("execution_estimate")

        if isinstance(
            metadata_estimate,
            Mapping,
        ):
            return dict(metadata_estimate)

        return None

    @staticmethod
    def _set_plan(
        opportunity: Any,
        plan: dict[str, Any],
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["execution"] = plan
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["execution"] = dict(plan)

    def plan_one(
        self,
        opportunity: Any,
    ) -> Any | None:
        result = opportunity

        estimate = self._estimate(result)

        if estimate is None:
            result = self.estimator.estimate_one(
                opportunity
            )

            if result is None:
                return None

            estimate = self._estimate(result)

        if estimate is None:
            raise ValueError(
                "Não foi possível gerar a "
                "estimativa de execução."
            )

        reason_codes: list[str] = []

        pipeline_approved = bool(
            self._read_field(
                result,
                "approved",
                False,
            )
        )

        if (
            self.require_pipeline_approval
            and not pipeline_approved
        ):
            reason_codes.append(
                "NOT_APPROVED"
            )

        known = bool(
            estimate.get(
                "known",
                False,
            )
        )

        if (
            self.require_known_slippage
            and not known
        ):
            reason_codes.append(
                "SLIPPAGE_UNKNOWN"
            )

        if (
            estimate.get(
                "slippage_acceptable"
            )
            is False
        ):
            reason_codes.append(
                "SLIPPAGE_EXCESSIVE"
            )

        adjusted_profit = estimate.get(
            "adjusted_profit"
        )

        if adjusted_profit is None:
            reason_codes.append(
                "PROFIT_UNKNOWN"
            )

        else:
            adjusted_profit = float(
                adjusted_profit
            )

            if adjusted_profit < self.min_profit:
                reason_codes.append(
                    "LOW_PROFIT"
                )

        approved = not reason_codes

        if approved:
            legacy_reason = "OK"

        elif reason_codes == ["LOW_PROFIT"]:
            legacy_reason = "Low Profit"

        else:
            legacy_reason = reason_codes[0]

        plan = {
            "approved": approved,
            "executable": approved,
            "status": (
                "APPROVED"
                if approved
                else "REJECTED"
            ),
            "reason": legacy_reason,
            "reason_codes": reason_codes,
            "adjusted_profit": (
                adjusted_profit
            ),
            "profit_unit": estimate.get(
                "profit_unit"
            ),
            "minimum_profit": (
                self.min_profit
            ),
            "slippage_known": known,
            "slippage_acceptable": (
                estimate.get(
                    "slippage_acceptable"
                )
            ),
            "mode": "PLAN",
            "planned_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

        self._set_plan(
            result,
            plan,
        )

        return result

    def plan(
        self,
        opportunities: Any,
    ) -> list[Any]:
        items = self._as_list(
            opportunities
        )

        planned: list[Any] = []
        invalid: list[dict[str, Any]] = []

        for index, opportunity in enumerate(
            items
        ):
            try:
                result = self.plan_one(
                    opportunity
                )

                if result is not None:
                    planned.append(result)

            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid.append(
                    {
                        "index": index,
                        "error": str(exc),
                    }
                )

        approved = sum(
            1
            for opportunity in planned
            if bool(
                self._read_field(
                    self._read_field(
                        opportunity,
                        "execution",
                        self._metadata(
                            opportunity
                        ).get(
                            "execution",
                            {},
                        ),
                    ),
                    "approved",
                    False,
                )
            )
        )

        self.last_report = {
            "input": len(items),
            "planned": len(planned),
            "approved": approved,
            "rejected": (
                len(planned) - approved
            ),
            "invalid": len(invalid),
            "details": invalid,
            "minimum_profit": (
                self.min_profit
            ),
        }

        return planned


execution_planner = ExecutionPlanner()