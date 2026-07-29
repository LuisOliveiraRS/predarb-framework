from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.events.event_bus import event_bus
from app.events.types.opportunity_found import (
    OpportunityFoundEvent,
)
from app.market.comparators.cross_platform import (
    CrossPlatformComparator,
)
from app.pipeline.pipeline_manager import (
    pipeline_manager,
)
from app.repositories.market_repository import (
    market_repository,
)


class ArbitrageEngine:
    """
    Engine principal de arbitragem do PredArb.

    Fluxo oficial:

        MarketRepository
            ↓
        CrossPlatformComparator
            ↓
        Pipeline analysis
            ↓
        EventBus
            ↓
        Resultado
    """

    ANALYSIS_PIPELINE = (
        pipeline_manager.ANALYSIS_PIPELINE
    )

    def __init__(self) -> None:
        self.comparator = (
            CrossPlatformComparator()
        )

    @staticmethod
    def _as_list(
        value: Any,
    ) -> list[Any]:
        """
        Normaliza resultados para lista.
        """

        if value is None:
            return []

        if isinstance(
            value,
            list,
        ):
            return value

        if isinstance(
            value,
            (str, bytes, dict),
        ):
            return [value]

        if isinstance(
            value,
            Iterable,
        ):
            return list(value)

        return [value]

    def load_markets(self) -> list[Any]:
        """
        Carrega os mercados do repositório oficial.
        """

        return self._as_list(
            market_repository.all()
        )

    def find_opportunities(
        self,
        markets: list[Any],
    ) -> list[Any]:
        """
        Compara mercados entre plataformas.
        """

        if not markets:
            return []

        opportunities = (
            self.comparator.compare(
                markets
            )
        )

        return self._as_list(
            opportunities
        )

    def process_pipeline(
        self,
        opportunities: list[Any],
    ) -> list[Any]:
        """
        Executa o Pipeline oficial de análise.
        """

        if not opportunities:
            return []

        result = pipeline_manager.run(
            opportunities,
            pipeline_name=(
                self.ANALYSIS_PIPELINE
            ),
        )

        return self._as_list(
            result
        )

    def publish_events(
        self,
        opportunities: list[Any],
    ) -> None:
        """
        Publica somente oportunidades aprovadas
        pelo Pipeline analysis.
        """

        for opportunity in opportunities:
            event_bus.publish(
                OpportunityFoundEvent(
                    opportunity
                )
            )

    def scan(
        self,
        *,
        publish: bool = True,
    ) -> list[Any]:
        """
        Executa o ciclo completo de arbitragem.

        O parâmetro publish=False permite consultar
        oportunidades sem gerar eventos novamente.
        """

        markets = self.load_markets()

        if not markets:
            return []

        opportunities = (
            self.find_opportunities(
                markets
            )
        )

        if not opportunities:
            return []

        analyzed = self.process_pipeline(
            opportunities
        )

        if not analyzed:
            return []

        if publish:
            self.publish_events(
                analyzed
            )

        return analyzed

    def paper_scan(self) -> Any:
        """
        Executa descoberta e Paper Trading.
        """

        markets = self.load_markets()

        opportunities = (
            self.find_opportunities(
                markets
            )
        )

        if not opportunities:
            return None

        return pipeline_manager.run(
            opportunities,
            pipeline_name=(
                pipeline_manager.PAPER_PIPELINE
            ),
        )

    def pipeline_status(
        self,
    ) -> dict[str, Any]:
        """
        Retorna a configuração e as métricas
        dos Pipelines.
        """

        return pipeline_manager.status()


arbitrage_engine = ArbitrageEngine()