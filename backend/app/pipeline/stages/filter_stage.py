from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class FilterStage(PipelineStage):
    """
    Remove oportunidades que não atendem aos
    critérios mínimos.

    Valores padrão preservados:

        MIN_ROI = 1.0
        MIN_PROFIT = 0.10
        MAX_RISK_SCORE = 80

    A liquidez somente será obrigatória quando
    require_liquidity=True.
    """

    MIN_ROI = 1.0
    MIN_PROFIT = 0.10
    MAX_RISK_SCORE = 80.0
    MIN_LIQUIDITY = 100.0

    def __init__(
        self,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
    ) -> None:
        self.min_roi = (
            self.MIN_ROI
            if min_roi is None
            else float(min_roi)
        )

        self.min_profit = (
            self.MIN_PROFIT
            if min_profit is None
            else float(min_profit)
        )

        self.max_risk_score = (
            self.MAX_RISK_SCORE
            if max_risk_score is None
            else float(max_risk_score)
        )

        self.min_liquidity = (
            self.MIN_LIQUIDITY
            if min_liquidity is None
            else float(min_liquidity)
        )

        self.require_liquidity = bool(
            require_liquidity,
        )

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
    ) -> float | None:
        if value is None or isinstance(
            value,
            bool,
        ):
            return None

        try:
            number = float(
                value,
            )

        except (TypeError, ValueError):
            return None

        if not isfinite(number):
            return None

        return number

    @staticmethod
    def _clone(
        opportunity: Any,
    ) -> Any:
        if isinstance(opportunity, Mapping):
            return dict(
                opportunity,
            )

        return copy(
            opportunity,
        )

    @staticmethod
    def _mark_approved(
        opportunity: Any,
    ) -> Any:
        result = FilterStage._clone(
            opportunity,
        )

        if isinstance(result, dict):
            result["approved"] = True
            return result

        if hasattr(result, "approved"):
            setattr(
                result,
                "approved",
                True,
            )

            return result

        metadata = getattr(
            result,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["approved"] = True

        return result

    @classmethod
    def _risk_score(
        cls,
        opportunity: Any,
    ) -> float:
        risk = cls._read_field(
            opportunity,
            "risk",
            None,
        )

        score = cls._read_field(
            risk,
            "score",
            None,
        )

        number = cls._number(
            score,
        )

        if number is None:
            return 100.0

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

        if isinstance(liquidity, Mapping):
            liquidity = liquidity.get(
                "available",
            )

        value = cls._number(
            liquidity,
        )

        if value is not None:
            return value

        return cls._number(
            cls._read_field(
                opportunity,
                "liquidity_value",
                None,
            )
        )

    def rejection_reasons(
        self,
        opportunity: Any,
    ) -> list[str]:
        """
        Retorna os motivos de rejeição.
        """

        reasons: list[str] = []

        roi = self._number(
            self._read_field(
                opportunity,
                "roi",
                None,
            )
        )

        profit = self._number(
            self._read_field(
                opportunity,
                "profit",
                None,
            )
        )

        risk_score = self._risk_score(
            opportunity,
        )

        if roi is None:
            reasons.append(
                "ROI ausente ou inválido.",
            )

        elif roi < self.min_roi:
            reasons.append(
                f"ROI abaixo de {self.min_roi}.",
            )

        if profit is None:
            reasons.append(
                "Lucro ausente ou inválido.",
            )

        elif profit < self.min_profit:
            reasons.append(
                "Lucro abaixo de "
                f"{self.min_profit}.",
            )

        if risk_score > self.max_risk_score:
            reasons.append(
                "Risco acima de "
                f"{self.max_risk_score}.",
            )

        if self.require_liquidity:
            liquidity = self._liquidity(
                opportunity,
            )

            if liquidity is None:
                reasons.append(
                    "Liquidez não informada.",
                )

            elif liquidity < self.min_liquidity:
                reasons.append(
                    "Liquidez abaixo de "
                    f"{self.min_liquidity}.",
                )

        return reasons

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or [],
        )

        approved: list[Any] = []
        rejected: list[dict[str, Any]] = []

        for index, opportunity in enumerate(
            opportunities,
        ):
            reasons = self.rejection_reasons(
                opportunity,
            )

            if reasons:
                rejected.append(
                    {
                        "index": index,
                        "question": (
                            self._read_field(
                                opportunity,
                                "question",
                                None,
                            )
                        ),
                        "reasons": reasons,
                    }
                )

                continue

            approved.append(
                self._mark_approved(
                    opportunity,
                )
            )

        context.opportunities = approved

        context.metadata["filter"] = {
            "input": len(opportunities),
            "approved": len(approved),
            "rejected": len(rejected),
            "details": rejected,
            "rules": {
                "min_roi": self.min_roi,
                "min_profit": (
                    self.min_profit
                ),
                "max_risk_score": (
                    self.max_risk_score
                ),
                "require_liquidity": (
                    self.require_liquidity
                ),
                "min_liquidity": (
                    self.min_liquidity
                ),
            },
        }

        return context