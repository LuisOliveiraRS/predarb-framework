from __future__ import annotations

from collections.abc import Callable, Iterable
from typing import Any

from app.core.settings import settings
from app.pipeline.pipeline import Pipeline
from app.pipeline.stages.ai_stage import AIStage
from app.pipeline.stages.enrich_stage import EnrichStage
from app.pipeline.stages.execution_stage import ExecutionStage
from app.pipeline.stages.filter_stage import FilterStage
from app.pipeline.stages.liquidity_stage import LiquidityStage
from app.pipeline.stages.order_stage import OrderStage
from app.pipeline.stages.paper_stage import PaperStage
from app.pipeline.stages.paper_account_stage import PaperAccountStage
from app.pipeline.stages.paper_risk_stage import PaperRiskStage
from app.pipeline.stages.portfolio_stage import PortfolioStage
from app.pipeline.stages.ranking_stage import RankingStage
from app.pipeline.stages.risk_stage import RiskStage
from app.pipeline.stages.slippage_stage import SlippageStage
from app.pipeline.stages.stake_stage import StakeStage
from app.pipeline.stages.validator_stage import ValidatorStage


class PipelineBuilder:
    """
    Construtor oficial dos Pipelines do PredArb.

    A análise AI é consultiva e é executada depois do cálculo de slippage,
    quando todas as features canônicas já estão disponíveis. O AIStage não
    filtra oportunidades e não substitui risco, ranking, portfólio ou execução.
    """

    ANALYSIS_NAME = "analysis"
    PAPER_NAME = "paper"
    LIVE_NAME = "live"

    def build(
        self,
        stages: Iterable[Any] | None = None,
        *,
        name: str | None = None,
        stop_on_error: bool = True,
    ) -> Pipeline:
        if stages is None:
            return self.build_analysis(
                name=name or self.ANALYSIS_NAME,
                stop_on_error=stop_on_error,
            )

        pipeline = Pipeline(
            name=name or "custom",
            stop_on_error=stop_on_error,
        )

        for stage in stages:
            pipeline.add_stage(stage)

        return pipeline

    def build_from_factories(
        self,
        factories: Iterable[Callable[[], Any]],
        *,
        name: str = "custom",
        stop_on_error: bool = True,
    ) -> Pipeline:
        stages: list[Any] = []

        for factory in factories:
            if not callable(factory):
                raise TypeError("Cada fábrica de estágio deve ser executável.")

            stage = factory()
            if stage is None:
                raise ValueError("Uma fábrica de estágio retornou None.")
            stages.append(stage)

        return self.build(
            stages,
            name=name,
            stop_on_error=stop_on_error,
        )

    @staticmethod
    def _resolve_ai_options(
        *,
        ai_enabled: bool | None,
        ai_strict_features: bool | None,
        ai_fail_on_error: bool | None,
    ) -> tuple[bool, bool, bool]:
        requested_enabled = True if ai_enabled is None else bool(ai_enabled)

        resolved_enabled = bool(
            settings.AI_ENABLED
            and settings.AI_PIPELINE_ENABLED
            and requested_enabled
        )

        resolved_strict = (
            settings.AI_STRICT_FEATURES
            if ai_strict_features is None
            else bool(ai_strict_features)
        )

        resolved_fail_on_error = (
            settings.AI_FAIL_ON_ERROR
            if ai_fail_on_error is None
            else bool(ai_fail_on_error)
        )

        return (
            resolved_enabled,
            resolved_strict,
            resolved_fail_on_error,
        )

    @staticmethod
    def _add_analysis_stages(
        pipeline: Pipeline,
        *,
        strict_validation: bool,
        require_liquidity: bool,
        min_roi: float | None,
        min_profit: float | None,
        max_risk_score: float | None,
        min_liquidity: float | None,
        bankroll_per_opportunity: float,
        total_bankroll: float,
        max_position_size: float,
        max_total_exposure: float,
        ranking_limit: int | None,
        max_slippage_rate: float | None,
        ai_enabled: bool,
        ai_strict_features: bool,
        ai_fail_on_error: bool,
    ) -> Pipeline:
        pipeline.add_stage(
            ValidatorStage(
                strict=strict_validation,
            )
        )

        pipeline.add_stage(EnrichStage())
        pipeline.add_stage(LiquidityStage())
        pipeline.add_stage(RiskStage())

        pipeline.add_stage(
            FilterStage(
                min_roi=min_roi,
                min_profit=min_profit,
                max_risk_score=max_risk_score,
                min_liquidity=min_liquidity,
                require_liquidity=require_liquidity,
            )
        )

        pipeline.add_stage(
            StakeStage(
                bankroll=bankroll_per_opportunity,
                strict=strict_validation,
            )
        )

        pipeline.add_stage(
            SlippageStage(
                require_liquidity=require_liquidity,
                max_slippage_rate=max_slippage_rate,
                strict=strict_validation,
            )
        )

        pipeline.add_stage(
            AIStage(
                enabled=ai_enabled,
                strict_features=ai_strict_features,
                fail_on_error=ai_fail_on_error,
            )
        )

        pipeline.add_stage(
            RankingStage(
                limit=ranking_limit,
            )
        )

        pipeline.add_stage(
            PortfolioStage(
                total_bankroll=total_bankroll,
                max_position_size=max_position_size,
                max_total_exposure=max_total_exposure,
            )
        )

        return pipeline

    def build_analysis(
        self,
        *,
        name: str = ANALYSIS_NAME,
        stop_on_error: bool = True,
        strict_validation: bool = False,
        require_liquidity: bool = False,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        bankroll_per_opportunity: float = 1_000.0,
        total_bankroll: float = 10_000.0,
        max_position_size: float = 0.10,
        max_total_exposure: float = 0.50,
        ranking_limit: int | None = None,
        max_slippage_rate: float | None = None,
        ai_enabled: bool | None = None,
        ai_strict_features: bool | None = None,
        ai_fail_on_error: bool | None = None,
    ) -> Pipeline:
        pipeline = Pipeline(
            name=name,
            stop_on_error=stop_on_error,
        )

        (
            resolved_ai_enabled,
            resolved_ai_strict_features,
            resolved_ai_fail_on_error,
        ) = self._resolve_ai_options(
            ai_enabled=ai_enabled,
            ai_strict_features=ai_strict_features,
            ai_fail_on_error=ai_fail_on_error,
        )

        return self._add_analysis_stages(
            pipeline,
            strict_validation=strict_validation,
            require_liquidity=require_liquidity,
            min_roi=min_roi,
            min_profit=min_profit,
            max_risk_score=max_risk_score,
            min_liquidity=min_liquidity,
            bankroll_per_opportunity=bankroll_per_opportunity,
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
            ranking_limit=ranking_limit,
            max_slippage_rate=max_slippage_rate,
            ai_enabled=resolved_ai_enabled,
            ai_strict_features=resolved_ai_strict_features,
            ai_fail_on_error=resolved_ai_fail_on_error,
        )

    def build_paper(
        self,
        *,
        name: str = PAPER_NAME,
        stop_on_error: bool = True,
        strict_validation: bool = False,
        require_liquidity: bool = False,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        bankroll_per_opportunity: float = 1_000.0,
        total_bankroll: float = 10_000.0,
        max_position_size: float = 0.10,
        max_total_exposure: float = 0.50,
        ranking_limit: int | None = None,
        max_slippage_rate: float | None = None,
        paper_fee_rate: float = 0.0,
        persist_paper_account: bool = False,
        paper_account: Any = None,
        paper_account_persist: bool = True,
        paper_risk_enabled: bool = False,
        paper_risk_guard: Any = None,
        paper_risk_strict: bool = False,
        ai_enabled: bool | None = None,
        ai_strict_features: bool | None = None,
        ai_fail_on_error: bool | None = None,
    ) -> Pipeline:
        pipeline = self.build_analysis(
            name=name,
            stop_on_error=stop_on_error,
            strict_validation=strict_validation,
            require_liquidity=require_liquidity,
            min_roi=min_roi,
            min_profit=min_profit,
            max_risk_score=max_risk_score,
            min_liquidity=min_liquidity,
            bankroll_per_opportunity=bankroll_per_opportunity,
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
            ranking_limit=ranking_limit,
            max_slippage_rate=max_slippage_rate,
            ai_enabled=ai_enabled,
            ai_strict_features=ai_strict_features,
            ai_fail_on_error=ai_fail_on_error,
        )

        pipeline.add_stage(
            PaperRiskStage(
                guard=paper_risk_guard,
                enabled=paper_risk_enabled,
                strict=paper_risk_strict,
            )
        )

        pipeline.add_stage(
            OrderStage(
                require_approved=True,
                strict=strict_validation,
            )
        )

        pipeline.add_stage(
            PaperStage(
                fee_rate=paper_fee_rate,
                strict=strict_validation,
            )
        )

        if persist_paper_account:
            pipeline.add_stage(
                PaperAccountStage(
                    account=paper_account,
                    persist=paper_account_persist,
                    enabled=True,
                )
            )

        return pipeline

    def build_live(
        self,
        *,
        executor: Any = None,
        enabled: bool = False,
        venue_resolver: Callable[[Any, Any], Any] | None = None,
        fail_fast: bool = True,
        name: str = LIVE_NAME,
        stop_on_error: bool = True,
        strict_validation: bool = False,
        require_liquidity: bool = False,
        min_roi: float | None = None,
        min_profit: float | None = None,
        max_risk_score: float | None = None,
        min_liquidity: float | None = None,
        bankroll_per_opportunity: float = 1_000.0,
        total_bankroll: float = 10_000.0,
        max_position_size: float = 0.10,
        max_total_exposure: float = 0.50,
        ranking_limit: int | None = None,
        max_slippage_rate: float | None = None,
        ai_enabled: bool | None = None,
        ai_strict_features: bool | None = None,
        ai_fail_on_error: bool | None = None,
    ) -> Pipeline:
        pipeline = self.build_analysis(
            name=name,
            stop_on_error=stop_on_error,
            strict_validation=strict_validation,
            require_liquidity=require_liquidity,
            min_roi=min_roi,
            min_profit=min_profit,
            max_risk_score=max_risk_score,
            min_liquidity=min_liquidity,
            bankroll_per_opportunity=bankroll_per_opportunity,
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
            ranking_limit=ranking_limit,
            max_slippage_rate=max_slippage_rate,
            ai_enabled=ai_enabled,
            ai_strict_features=ai_strict_features,
            ai_fail_on_error=ai_fail_on_error,
        )

        pipeline.add_stage(
            OrderStage(
                require_approved=True,
                strict=strict_validation,
            )
        )

        pipeline.add_stage(
            ExecutionStage(
                executor=executor,
                enabled=enabled,
                venue_resolver=venue_resolver,
                fail_fast=fail_fast,
            )
        )

        return pipeline


pipeline_builder = PipelineBuilder()
