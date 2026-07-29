from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any

from app.engine.slippage_calculator import (
    SlippageCalculator,
    slippage_calculator,
)


class ExecutionEstimator:
    """
    Estima o resultado financeiro após o slippage.

    Não executa ordens.

    Quando existe stake, adjusted_profit representa
    um valor financeiro.

    Quando não existe stake, adjusted_profit representa
    pontos percentuais da margem probabilística.
    O campo profit_unit identifica a unidade.
    """

    def __init__(
        self,
        *,
        calculator: SlippageCalculator | None = None,
        require_liquidity: bool = False,
        max_slippage_rate: float | None = None,
        strict: bool = False,
    ) -> None:
        self.calculator = (
            calculator or slippage_calculator
        )

        self.require_liquidity = bool(
            require_liquidity
        )

        self.max_slippage_rate = (
            max_slippage_rate
        )

        self.strict = bool(strict)

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
    def _number(
        value: Any,
        default: float | None = None,
    ) -> float | None:
        if value is None or isinstance(
            value,
            bool,
        ):
            return default

        try:
            number = float(value)

        except (TypeError, ValueError):
            return default

        if not isfinite(number):
            return default

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
    def _slippage_analysis(
        cls,
        opportunity: Any,
    ) -> dict[str, Any]:
        analysis = cls._read_field(
            opportunity,
            "slippage",
            None,
        )

        if isinstance(analysis, Mapping) and analysis:
            return dict(analysis)

        metadata_analysis = cls._metadata(
            opportunity
        ).get("slippage")

        if isinstance(
            metadata_analysis,
            Mapping,
        ):
            return dict(metadata_analysis)

        return {}

    @classmethod
    def _stake_total(
        cls,
        opportunity: Any,
    ) -> float | None:
        stake = cls._read_field(
            opportunity,
            "stake",
            None,
        )

        total = cls._read_field(
            stake,
            "total",
            None,
        )

        if total is None:
            total = cls._read_field(
                stake,
                "amount",
                None,
            )

        return cls._number(total)

    @staticmethod
    def _set_estimate(
        opportunity: Any,
        estimate: dict[str, Any],
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["adjusted_cost"] = (
                estimate["adjusted_cost"]
            )

            opportunity["adjusted_profit"] = (
                estimate["adjusted_profit"]
            )

            opportunity["adjusted_roi"] = (
                estimate["adjusted_roi"]
            )

            opportunity["execution_estimate"] = (
                estimate
            )

            return

        if hasattr(
            opportunity,
            "adjusted_profit",
        ):
            opportunity.adjusted_profit = (
                estimate["adjusted_profit"]
            )

        if hasattr(
            opportunity,
            "adjusted_roi",
        ):
            opportunity.adjusted_roi = (
                estimate["adjusted_roi"]
            )

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["adjusted_cost"] = (
                estimate["adjusted_cost"]
            )

            metadata["execution_estimate"] = dict(
                estimate
            )

    def estimate_one(
        self,
        opportunity: Any,
    ) -> Any | None:
        result = self.calculator.calculate_one(
            opportunity,
            require_liquidity=(
                self.require_liquidity
            ),
            max_slippage_rate=(
                self.max_slippage_rate
            ),
            strict=self.strict,
        )

        if result is None:
            return None

        slippage = self._slippage_analysis(
            result
        )

        known = bool(
            slippage.get(
                "known",
                False,
            )
        )

        rate = self._number(
            slippage.get("rate")
        )

        base_cost = self._number(
            self._read_field(
                result,
                "cost",
                None,
            )
        )

        adjusted_cost = (
            base_cost + rate
            if (
                base_cost is not None
                and rate is not None
            )
            else None
        )

        stake_total = self._stake_total(
            result
        )

        adjusted_profit = self._number(
            slippage.get(
                "adjusted_profit"
            )
        )

        adjusted_roi = self._number(
            slippage.get(
                "adjusted_roi"
            )
        )

        if (
            adjusted_profit is not None
            and stake_total is not None
            and stake_total > 0
        ):
            profit_unit = "currency"

        elif adjusted_cost is not None:
            adjusted_profit = max(
                0.0,
                1.0 - adjusted_cost,
            ) * 100

            adjusted_roi = adjusted_profit

            profit_unit = "percentage_points"

        else:
            adjusted_profit = None
            adjusted_roi = None
            profit_unit = "unknown"

        profitable = (
            adjusted_profit is not None
            and adjusted_profit > 0
        )

        if not known:
            status = "UNKNOWN"

        elif profitable:
            status = "PROFITABLE"

        else:
            status = "UNPROFITABLE"

        estimate = {
            "known": known,
            "status": status,
            "base_cost": (
                round(base_cost, 6)
                if base_cost is not None
                else None
            ),
            "adjusted_cost": (
                round(adjusted_cost, 6)
                if adjusted_cost is not None
                else None
            ),
            "slippage_rate": (
                round(rate, 6)
                if rate is not None
                else None
            ),
            "slippage_cost": (
                slippage.get("cost")
            ),
            "adjusted_profit": (
                round(adjusted_profit, 2)
                if adjusted_profit is not None
                else None
            ),
            "adjusted_roi": (
                round(adjusted_roi, 4)
                if adjusted_roi is not None
                else None
            ),
            "profit_unit": profit_unit,
            "profitable": profitable,
            "slippage_acceptable": (
                slippage.get("acceptable")
            ),
        }

        self._set_estimate(
            result,
            estimate,
        )

        return result

    def estimate(
        self,
        opportunities: Any,
    ) -> list[Any]:
        items = self._as_list(
            opportunities
        )

        estimated: list[Any] = []
        invalid: list[dict[str, Any]] = []

        for index, opportunity in enumerate(
            items
        ):
            try:
                result = self.estimate_one(
                    opportunity
                )

                if result is not None:
                    estimated.append(result)

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

                if self.strict:
                    raise

        self.last_report = {
            "input": len(items),
            "estimated": len(estimated),
            "invalid": len(invalid),
            "details": invalid,
        }

        return estimated


execution_estimator = ExecutionEstimator()