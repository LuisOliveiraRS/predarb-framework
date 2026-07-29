from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.stages.filter_stage import (
    FilterStage,
)


class OpportunityFilter:
    """
    Fachada de compatibilidade para
    o FilterStage oficial.
    """

    MIN_ROI = FilterStage.MIN_ROI
    MIN_PROFIT = FilterStage.MIN_PROFIT
    MAX_RISK_SCORE = (
        FilterStage.MAX_RISK_SCORE
    )
    MIN_LIQUIDITY = (
        FilterStage.MIN_LIQUIDITY
    )

    def __init__(
        self,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
    ) -> None:
        self.min_roi = min_roi
        self.min_profit = min_profit
        self.max_risk_score = (
            max_risk_score
        )
        self.min_liquidity = (
            min_liquidity
        )
        self.require_liquidity = bool(
            require_liquidity
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

    def _stage(
        self,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool | None = None,
    ) -> FilterStage:
        return FilterStage(
            min_roi=(
                self.min_roi
                if min_roi is None
                else min_roi
            ),
            min_profit=(
                self.min_profit
                if min_profit is None
                else min_profit
            ),
            max_risk_score=(
                self.max_risk_score
                if max_risk_score is None
                else max_risk_score
            ),
            min_liquidity=(
                self.min_liquidity
                if min_liquidity is None
                else min_liquidity
            ),
            require_liquidity=(
                self.require_liquidity
                if require_liquidity is None
                else require_liquidity
            ),
        )

    def is_approved(
        self,
        opportunity: Any,
        **options: Any,
    ) -> bool:
        """
        Verifica uma única oportunidade.
        """

        stage = self._stage(
            **options
        )

        return not stage.rejection_reasons(
            opportunity
        )

    def filter(
        self,
        opportunities: Any,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool | None = None,
    ) -> list[Any]:
        context = PipelineContext(
            {
                "opportunities": self._as_list(
                    opportunities
                ),
            }
        )

        stage = self._stage(
            min_roi=min_roi,
            min_profit=min_profit,
            max_risk_score=max_risk_score,
            min_liquidity=min_liquidity,
            require_liquidity=(
                require_liquidity
            ),
        )

        stage.process(
            context
        )

        self.last_report = dict(
            context.metadata.get(
                "filter",
                {},
            )
        )

        return list(
            context.opportunities
            or []
        )


opportunity_filter = OpportunityFilter()