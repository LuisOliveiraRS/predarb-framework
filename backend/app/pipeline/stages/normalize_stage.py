from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage
from app.services.market_service import market_service


class NormalizeStage(PipelineStage):
    """
    Normaliza a entrada do Pipeline.

    Responsabilidades:

    - normalizar mercados usando MarketService;
    - preservar objetos e dicionários;
    - organizar mercados de forma determinística;
    - transformar coleções de oportunidades em listas.

    O estágio não cria oportunidades e não executa
    comparação entre plataformas.
    """

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um campo de dicionário ou objeto.
        """

        if isinstance(target, Mapping):
            return target.get(
                field_name,
                default,
            )

        return getattr(
            target,
            field_name,
            default,
        )

    @classmethod
    def _market_sort_key(
        cls,
        market: Any,
    ) -> tuple[str, str]:
        """
        Gera uma chave estável para ordenar mercados.
        """

        question = cls._read_field(
            market,
            "question",
            "",
        )

        platform = cls._read_field(
            market,
            "platform",
            "",
        )

        return (
            str(question).strip().casefold(),
            str(platform).strip().casefold(),
        )

    def process(
        self,
        context: Any,
    ) -> Any:
        """
        Normaliza os dados disponíveis no contexto.
        """

        normalized_markets = 0
        normalized_opportunities = 0

        if context.markets is not None:
            markets = market_service.normalize(
                context.markets,
            )

            markets.sort(
                key=self._market_sort_key,
            )

            context.markets = markets

            normalized_markets = len(
                markets,
            )

        if context.opportunities is not None:
            if isinstance(
                context.opportunities,
                (str, bytes, Mapping),
            ):
                raise TypeError(
                    "context.opportunities deve ser "
                    "uma coleção de oportunidades."
                )

            context.opportunities = list(
                context.opportunities,
            )

            normalized_opportunities = len(
                context.opportunities,
            )

        context.metadata["normalize"] = {
            "markets": normalized_markets,
            "opportunities": (
                normalized_opportunities
            ),
        }

        return context