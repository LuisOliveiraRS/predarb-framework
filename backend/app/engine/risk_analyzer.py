from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.stages.risk_stage import (
    RiskStage,
)


class RiskAnalyzer:
    """
    Fachada de compatibilidade para
    o RiskStage oficial.
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
        return RiskStage().analyze_opportunity(
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

        RiskStage().process(
            context
        )

        self.last_report = dict(
            context.metadata.get(
                "risk",
                {},
            )
        )

        return list(
            context.opportunities
            or []
        )


risk_analyzer = RiskAnalyzer()