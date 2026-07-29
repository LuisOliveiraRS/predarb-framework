from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.portfolio_stage import PortfolioStage


class PortfolioManager:
    """
    Fachada de compatibilidade para o PortfolioStage.

    Responsabilidades:

    - simular a alocação do bankroll;
    - aplicar o limite por posição;
    - aplicar o limite de exposição total;
    - retornar somente oportunidades aprovadas;
    - não reservar capital real;
    - não criar posições.

    A reserva efetiva do bankroll deverá ocorrer
    somente após a confirmação da execução.
    """

    DEFAULT_TOTAL_BANKROLL = 10_000.0
    DEFAULT_MAX_POSITION_SIZE = 0.10
    DEFAULT_MAX_TOTAL_EXPOSURE = 0.50

    def __init__(
        self,
        *,
        total_bankroll: float = DEFAULT_TOTAL_BANKROLL,
        max_position_size: float = DEFAULT_MAX_POSITION_SIZE,
        max_total_exposure: float = DEFAULT_MAX_TOTAL_EXPOSURE,
    ) -> None:
        stage = PortfolioStage(
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
        )

        self.total_bankroll = stage.total_bankroll
        self.max_position_size = stage.max_position_size
        self.max_total_exposure = stage.max_total_exposure

        self.available = self.total_bankroll
        self.allocated = 0.0

        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(
        opportunities: Any,
    ) -> list[Any]:
        """
        Normaliza uma oportunidade ou coleção
        de oportunidades para uma lista.
        """

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
                "opportunities deve ser uma coleção "
                "de oportunidades."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(opportunities)

        return [opportunities]

    def _stage(
        self,
        *,
        total_bankroll: float | None = None,
        max_position_size: float | None = None,
        max_total_exposure: float | None = None,
    ) -> PortfolioStage:
        """
        Cria uma nova instância do estágio para
        cada processamento.

        Isso impede compartilhamento acidental
        de estado entre execuções.
        """

        return PortfolioStage(
            total_bankroll=(
                self.total_bankroll
                if total_bankroll is None
                else total_bankroll
            ),
            max_position_size=(
                self.max_position_size
                if max_position_size is None
                else max_position_size
            ),
            max_total_exposure=(
                self.max_total_exposure
                if max_total_exposure is None
                else max_total_exposure
            ),
        )

    @staticmethod
    def _synchronize_model(
        opportunity: Any,
    ) -> None:
        """
        Sincroniza a análise de portfólio quando
        a oportunidade é um objeto Opportunity.

        O PortfolioStage armazena dados desconhecidos
        dentro de metadata para manter compatibilidade
        com objetos genéricos.
        """

        if isinstance(
            opportunity,
            Mapping,
        ):
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if not isinstance(
            metadata,
            dict,
        ):
            return

        portfolio_data = metadata.get(
            "portfolio"
        )

        if not isinstance(
            portfolio_data,
            Mapping,
        ):
            return

        if hasattr(
            opportunity,
            "portfolio",
        ):
            opportunity.portfolio = dict(
                portfolio_data
            )

    def process(
        self,
        opportunities: Any,
        *,
        total_bankroll: float | None = None,
        max_position_size: float | None = None,
        max_total_exposure: float | None = None,
    ) -> list[Any]:
        """
        Simula a alocação das oportunidades.

        Preserva a assinatura principal da
        implementação anterior:

            portfolio_manager.process(opportunities)

        O resultado contém somente as oportunidades
        aprovadas.
        """

        items = self._as_list(
            opportunities
        )

        context = PipelineContext(
            {
                "opportunities": items,
            }
        )

        stage = self._stage(
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
        )

        stage.process(
            context
        )

        approved = list(
            context.opportunities
            or []
        )

        for opportunity in approved:
            self._synchronize_model(
                opportunity
            )

        self.last_report = dict(
            context.metadata.get(
                "portfolio",
                {},
            )
        )

        self.available = float(
            self.last_report.get(
                "available",
                stage.total_bankroll,
            )
        )

        self.allocated = float(
            self.last_report.get(
                "allocated",
                0.0,
            )
        )

        return approved

    def process_one(
        self,
        opportunity: Any,
        *,
        total_bankroll: float | None = None,
        max_position_size: float | None = None,
        max_total_exposure: float | None = None,
    ) -> Any | None:
        """
        Simula a alocação de uma oportunidade.
        """

        approved = self.process(
            [opportunity],
            total_bankroll=total_bankroll,
            max_position_size=max_position_size,
            max_total_exposure=max_total_exposure,
        )

        return (
            approved[0]
            if approved
            else None
        )

    def reset(self) -> None:
        """
        Limpa apenas o estado informativo da fachada.

        Nenhum bankroll real é alterado porque esta
        implementação trabalha em modo de simulação.
        """

        self.available = self.total_bankroll
        self.allocated = 0.0
        self.last_report = {}

    @property
    def utilization(self) -> float:
        """
        Retorna a utilização simulada do bankroll.
        """

        if self.total_bankroll <= 0:
            return 0.0

        return round(
            self.allocated
            / self.total_bankroll,
            4,
        )

    def status(self) -> dict[str, Any]:
        """
        Retorna a configuração e o último resultado.
        """

        return {
            "mode": "simulation",
            "total_bankroll": self.total_bankroll,
            "available": self.available,
            "allocated": self.allocated,
            "utilization": self.utilization,
            "max_position_size": (
                self.max_position_size
            ),
            "max_total_exposure": (
                self.max_total_exposure
            ),
            "last_report": dict(
                self.last_report
            ),
        }


portfolio_manager = PortfolioManager()