from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.stages.enrich_stage import (
    EnrichStage,
)


class OpportunityEnricher:
    """
    Fachada de compatibilidade para
    o EnrichStage oficial.
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

    def enrich_one(
        self,
        opportunity: Any,
    ) -> Any:
        return EnrichStage().enrich_opportunity(
            opportunity
        )

    def enrich(
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

        EnrichStage().process(
            context
        )

        self.last_report = dict(
            context.metadata.get(
                "enrichment",
                {},
            )
        )

        return list(
            context.opportunities
            or []
        )


opportunity_enricher = OpportunityEnricher()