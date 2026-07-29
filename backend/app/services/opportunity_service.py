from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.services.comparator_service import (
    comparator_service,
)
from app.services.liquidity_service import (
    liquidity_service,
)
from app.services.opportunity_filter_service import (
    opportunity_filter_service,
)
from app.services.ranking_service import (
    ranking_service,
)


class OpportunityService:
    """
    Serviço central para geração e preparação
    de oportunidades.

    Fluxo completo opcional:

        Mercados
            ↓
        ComparatorService
            ↓
        OpportunityFilterService
            ↓
        LiquidityService
            ↓
        RankingService
    """

    def generate(
        self,
        markets: Iterable[Any] | None,
    ) -> list[Any]:
        """
        Gera oportunidades a partir de mercados.

        Preserva a interface original do serviço.
        """

        return comparator_service.compare(
            markets,
        )

    def prepare(
        self,
        opportunities: Iterable[Any] | None,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
        limit: int | None = None,
    ) -> list[Any]:
        """
        Filtra, valida liquidez e ordena
        oportunidades já geradas.
        """

        filtered = (
            opportunity_filter_service.filter(
                opportunities,
                min_roi=min_roi,
                min_profit=min_profit,
            )
        )

        liquid = liquidity_service.validate(
            filtered,
            min_liquidity=min_liquidity,
            require_liquidity=require_liquidity,
        )

        return ranking_service.rank(
            liquid,
            limit=limit,
        )

    def generate_and_prepare(
        self,
        markets: Iterable[Any] | None,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
        limit: int | None = None,
    ) -> list[Any]:
        """
        Executa o fluxo completo de geração,
        validação e ranking.
        """

        opportunities = self.generate(
            markets,
        )

        return self.prepare(
            opportunities,
            min_roi=min_roi,
            min_profit=min_profit,
            min_liquidity=min_liquidity,
            require_liquidity=require_liquidity,
            limit=limit,
        )


opportunity_service = OpportunityService()