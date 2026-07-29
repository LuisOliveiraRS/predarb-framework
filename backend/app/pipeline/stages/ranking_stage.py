from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class RankingStage(PipelineStage):
    """
    Calcula o score institucional e ordena as
    oportunidades da melhor para a pior.

    Fórmula preservada:

        ROI        × 0,35
        lucro      × 0,30
        confiança  × 0,20
        edge × 100 × 0,10
        risco      × 0,05 como penalidade
    """

    def __init__(
        self,
        *,
        limit: int | None = None,
    ) -> None:
        if limit is not None:
            if not isinstance(limit, int):
                raise TypeError(
                    "O limite do ranking "
                    "deve ser inteiro."
                )

            if limit < 0:
                raise ValueError(
                    "O limite do ranking não "
                    "pode ser negativo."
                )

        self.limit = limit

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

    @classmethod
    def _number(
        cls,
        value: Any,
        default: float = 0.0,
    ) -> float:
        if (
            value is None
            or isinstance(value, bool)
        ):
            return float(default)

        try:
            number = float(value)

        except (TypeError, ValueError):
            return float(default)

        if not isfinite(number):
            return float(default)

        return number

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

        return cls._number(
            cls._read_field(
                risk,
                "score",
                100.0,
            ),
            100.0,
        )

    @classmethod
    def calculate_score(
        cls,
        opportunity: Any,
    ) -> float:
        roi = cls._number(
            cls._read_field(
                opportunity,
                "roi",
                0.0,
            )
        )

        profit = cls._number(
            cls._read_field(
                opportunity,
                "profit",
                0.0,
            )
        )

        confidence = cls._number(
            cls._read_field(
                opportunity,
                "confidence",
                0.0,
            )
        )

        if 0 <= confidence <= 1:
            confidence *= 100

        edge = cls._number(
            cls._read_field(
                opportunity,
                "edge",
                0.0,
            )
        )

        risk_score = cls._risk_score(
            opportunity,
        )

        score = (
            roi * 0.35
            + profit * 0.30
            + confidence * 0.20
            + edge * 100 * 0.10
            - risk_score * 0.05
        )

        return round(
            score,
            2,
        )

    @staticmethod
    def _set_score(
        opportunity: Any,
        score: float,
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["score"] = score
            return

        if hasattr(
            opportunity,
            "score",
        ):
            opportunity.score = score
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["score"] = score

    def rank_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        result = deepcopy(
            opportunity,
        )

        score = self.calculate_score(
            opportunity,
        )

        self._set_score(
            result,
            score,
        )

        return result

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or [],
        )

        ranked = [
            self.rank_opportunity(
                opportunity,
            )
            for opportunity in opportunities
        ]

        ranked.sort(
            key=self.calculate_score,
            reverse=True,
        )

        if self.limit is not None:
            ranked = ranked[
                : self.limit
            ]

        context.opportunities = ranked

        context.metadata["ranking"] = {
            "input": len(opportunities),
            "ranked": len(ranked),
            "limit": self.limit,
            "top_score": (
                self.calculate_score(
                    ranked[0]
                )
                if ranked
                else None
            ),
        }

        return context

    execute = process