from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class SlippageStage(PipelineStage):
    """
    Estima o impacto do slippage sem alterar os
    valores financeiros originais da oportunidade.

    Faixas preservadas da implementação existente:

        liquidez >= 10.000 -> 0,10%
        liquidez >=  5.000 -> 0,30%
        liquidez >=  2.000 -> 0,70%
        liquidez <   2.000 -> 1,50%

    Quando a liquidez não estiver disponível, o
    estágio registra o estado UNKNOWN e não inventa
    uma taxa de slippage.
    """

    HIGH_LIQUIDITY = 10_000.0
    MEDIUM_LIQUIDITY = 5_000.0
    LOW_LIQUIDITY = 2_000.0

    HIGH_RATE = 0.001
    MEDIUM_RATE = 0.003
    LOW_RATE = 0.007
    VERY_LOW_RATE = 0.015

    def __init__(
        self,
        *,
        require_liquidity: bool = False,
        max_slippage_rate: float | None = None,
        strict: bool = False,
    ) -> None:
        self.require_liquidity = bool(
            require_liquidity
        )

        self.strict = bool(
            strict
        )

        if max_slippage_rate is None:
            self.max_slippage_rate = None

        else:
            self.max_slippage_rate = (
                self._non_negative_number(
                    max_slippage_rate,
                    "max_slippage_rate",
                )
            )

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(
            target,
            Mapping,
        ):
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
        field_name: str,
    ) -> float:
        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if not isfinite(
            number
        ):
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser finito."
            )

        return number

    @classmethod
    def _non_negative_number(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        number = cls._number(
            value,
            field_name,
        )

        if number < 0:
            raise ValueError(
                f"O campo {field_name!r} "
                "não pode ser negativo."
            )

        return number

    @classmethod
    def _liquidity(
        cls,
        opportunity: Any,
    ) -> float | None:
        liquidity = cls._read_field(
            opportunity,
            "liquidity",
            None,
        )

        if isinstance(
            liquidity,
            Mapping,
        ):
            liquidity = liquidity.get(
                "available"
            )

        if liquidity is None:
            liquidity = cls._read_field(
                opportunity,
                "liquidity_value",
                None,
            )

        if liquidity is None:
            return None

        try:
            return cls._non_negative_number(
                liquidity,
                "liquidity",
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

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
            return None

        try:
            return cls._non_negative_number(
                total,
                "stake.total",
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

    @classmethod
    def _base_profit(
        cls,
        opportunity: Any,
    ) -> float | None:
        stake = cls._read_field(
            opportunity,
            "stake",
            None,
        )

        candidates = (
            cls._read_field(
                stake,
                "guaranteed_profit",
                None,
            ),
            cls._read_field(
                opportunity,
                "expected_profit",
                None,
            ),
            cls._read_field(
                opportunity,
                "profit",
                None,
            ),
        )

        for candidate in candidates:
            if candidate is None:
                continue

            try:
                return cls._number(
                    candidate,
                    "profit",
                )

            except (
                TypeError,
                ValueError,
            ):
                continue

        return None

    @classmethod
    def _rate_for_liquidity(
        cls,
        liquidity: float,
    ) -> float:
        if liquidity >= cls.HIGH_LIQUIDITY:
            return cls.HIGH_RATE

        if liquidity >= cls.MEDIUM_LIQUIDITY:
            return cls.MEDIUM_RATE

        if liquidity >= cls.LOW_LIQUIDITY:
            return cls.LOW_RATE

        return cls.VERY_LOW_RATE

    @staticmethod
    def _set_analysis(
        opportunity: Any,
        analysis: dict[str, Any],
    ) -> None:
        if isinstance(
            opportunity,
            dict,
        ):
            opportunity["slippage"] = (
                analysis
            )

            opportunity["slippage_rate"] = (
                analysis["rate"]
            )

            opportunity["slippage_cost"] = (
                analysis["cost"]
            )

            opportunity["adjusted_profit"] = (
                analysis["adjusted_profit"]
            )

            opportunity["adjusted_roi"] = (
                analysis["adjusted_roi"]
            )

            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(
            metadata,
            dict,
        ):
            metadata["slippage"] = dict(
                analysis
            )

    def analyze_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        result = deepcopy(
            opportunity
        )

        liquidity = self._liquidity(
            opportunity
        )

        stake_total = self._stake_total(
            opportunity
        )

        base_profit = self._base_profit(
            opportunity
        )

        if liquidity is None:
            if self.require_liquidity:
                raise ValueError(
                    "A oportunidade não possui "
                    "liquidez válida."
                )

            analysis = {
                "known": False,
                "liquidity": None,
                "rate": None,
                "percentage": None,
                "cost": None,
                "base_profit": base_profit,
                "adjusted_profit": None,
                "adjusted_roi": None,
                "acceptable": None,
                "status": "UNKNOWN",
            }

            self._set_analysis(
                result,
                analysis,
            )

            return result

        rate = self._rate_for_liquidity(
            liquidity
        )

        slippage_cost = (
            stake_total * rate
            if stake_total is not None
            else None
        )

        adjusted_profit = (
            base_profit - slippage_cost
            if (
                base_profit is not None
                and slippage_cost is not None
            )
            else None
        )

        adjusted_roi = (
            adjusted_profit
            / stake_total
            * 100
            if (
                adjusted_profit is not None
                and stake_total is not None
                and stake_total > 0
            )
            else None
        )

        acceptable = (
            True
            if self.max_slippage_rate is None
            else rate
            <= self.max_slippage_rate
        )

        analysis = {
            "known": True,
            "liquidity": round(
                liquidity,
                2,
            ),
            "rate": round(
                rate,
                6,
            ),
            "percentage": round(
                rate * 100,
                4,
            ),
            "cost": (
                round(
                    slippage_cost,
                    2,
                )
                if slippage_cost is not None
                else None
            ),
            "base_profit": (
                round(
                    base_profit,
                    2,
                )
                if base_profit is not None
                else None
            ),
            "adjusted_profit": (
                round(
                    adjusted_profit,
                    2,
                )
                if adjusted_profit is not None
                else None
            ),
            "adjusted_roi": (
                round(
                    adjusted_roi,
                    4,
                )
                if adjusted_roi is not None
                else None
            ),
            "acceptable": acceptable,
            "status": (
                "ACCEPTABLE"
                if acceptable
                else "EXCESSIVE"
            ),
        }

        self._set_analysis(
            result,
            analysis,
        )

        return result

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or []
        )

        analyzed: list[Any] = []
        invalid: list[
            dict[str, Any]
        ] = []

        for index, opportunity in enumerate(
            opportunities
        ):
            try:
                analyzed.append(
                    self.analyze_opportunity(
                        opportunity
                    )
                )

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

        context.opportunities = analyzed

        known = sum(
            1
            for opportunity in analyzed
            if self._read_field(
                self._read_field(
                    opportunity,
                    "slippage",
                    {},
                ),
                "known",
                False,
            )
        )

        excessive = sum(
            1
            for opportunity in analyzed
            if self._read_field(
                self._read_field(
                    opportunity,
                    "slippage",
                    {},
                ),
                "status",
                None,
            )
            == "EXCESSIVE"
        )

        context.metadata["slippage"] = {
            "input": len(
                opportunities
            ),
            "analyzed": len(
                analyzed
            ),
            "known": known,
            "unknown": (
                len(analyzed)
                - known
            ),
            "excessive": excessive,
            "invalid": len(
                invalid
            ),
            "details": invalid,
            "max_slippage_rate": (
                self.max_slippage_rate
            ),
        }

        return context

    execute = process