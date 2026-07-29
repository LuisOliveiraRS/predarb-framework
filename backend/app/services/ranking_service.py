from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import inf
from typing import Any


class RankingService:
    """
    Ordena oportunidades usando os critérios:

    1. maior ROI;
    2. maior lucro.

    O serviço preserva os objetos originais,
    alterando apenas sua ordem.
    """

    @staticmethod
    def _read_field(
        opportunity: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um campo de dicionário ou objeto.
        """

        if isinstance(
            opportunity,
            Mapping,
        ):
            return opportunity.get(
                field_name,
                default,
            )

        return getattr(
            opportunity,
            field_name,
            default,
        )

    @staticmethod
    def _number_or_minimum(
        value: Any,
    ) -> float:
        """
        Converte valores válidos para float.

        Valores inválidos recebem prioridade mínima
        e são enviados para o final do ranking.
        """

        if value is None or isinstance(
            value,
            bool,
        ):
            return -inf

        try:
            return float(value)

        except (TypeError, ValueError):
            return -inf

    def score_key(
        self,
        opportunity: Any,
    ) -> tuple[float, float]:
        """
        Gera a chave usada na ordenação.
        """

        roi = self._number_or_minimum(
            self._read_field(
                opportunity,
                "roi",
            )
        )

        profit = self._number_or_minimum(
            self._read_field(
                opportunity,
                "profit",
            )
        )

        return (
            roi,
            profit,
        )

    def rank(
        self,
        opportunities: Iterable[Any] | None,
        *,
        limit: int | None = None,
    ) -> list[Any]:
        """
        Ordena oportunidades por ROI e lucro.
        """

        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "Opportunities deve ser uma coleção."
            )

        ranked = sorted(
            list(opportunities),
            key=self.score_key,
            reverse=True,
        )

        if limit is None:
            return ranked

        if not isinstance(
            limit,
            int,
        ):
            raise TypeError(
                "O limite do ranking deve ser inteiro."
            )

        if limit < 0:
            raise ValueError(
                "O limite do ranking não pode "
                "ser negativo."
            )

        return ranked[:limit]


ranking_service = RankingService()