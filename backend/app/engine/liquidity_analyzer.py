from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.stages.liquidity_stage import (
    LiquidityStage,
)


class LiquidityAnalyzer:
    """
    Fachada de compatibilidade para
    o LiquidityStage oficial.

    Não utiliza mais liquidez fictícia
    de 1.000 quando os dados estão ausentes.
    """

    def __init__(self) -> None:
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
                "opportunities deve ser "
                "uma coleção."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(
                opportunities
            )

        return [opportunities]

    def analyze_one(
        self,
        opportunity: Any,
    ) -> Any:
        return LiquidityStage().analyze_opportunity(
            opportunity
        )

    def analyze(
        self,
        opportunities: Any,
    ) -> list[Any]:
        context = PipelineContext(
            {
                "opportunities": self._as_list(
                    opportunities
                ),
            }
        )

        LiquidityStage().process(
            context
        )

        self.last_report = dict(
            context.metadata.get(
                "liquidity",
                {},
            )
        )

        return list(
            context.opportunities
            or []
        )


liquidity_analyzer = LiquidityAnalyzer()