from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.ranking_stage import RankingStage


class OpportunityRanker:
    """
    Fachada de compatibilidade para o RankingStage.

    A fórmula oficial passa a existir somente em:

        app.pipeline.stages.ranking_stage
    """

    def __init__(
        self,
        *,
        limit: int | None = None,
    ) -> None:
        self.limit = limit
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
    def calculate_score(
        opportunity: Any,
    ) -> float:
        return RankingStage.calculate_score(
            opportunity
        )

    def rank_one(
        self,
        opportunity: Any,
    ) -> Any:
        return RankingStage().rank_opportunity(
            opportunity
        )

    def rank(
        self,
        opportunities: Any,
        *,
        limit: int | None = None,
    ) -> list[Any]:
        resolved_limit = (
            self.limit
            if limit is None
            else limit
        )

        context = PipelineContext(
            {
                "opportunities": self._as_list(
                    opportunities
                ),
            }
        )

        RankingStage(
            limit=resolved_limit
        ).process(context)

        self.last_report = dict(
            context.metadata.get(
                "ranking",
                {},
            )
        )

        return list(
            context.opportunities or []
        )


opportunity_ranker = OpportunityRanker()