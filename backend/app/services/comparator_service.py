from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.market.comparators.cross_platform import (
    cross_platform_comparator,
)


class ComparatorService:
    """
    Fachada da camada de serviços para o
    comparador oficial entre plataformas.

    Responsabilidades:

    - validar a coleção de mercados;
    - executar a comparação;
    - normalizar o resultado para lista;
    - impedir que valores None avancem no fluxo.
    """

    def __init__(
        self,
        comparator: Any = None,
    ) -> None:
        self._comparator = (
            comparator
            or cross_platform_comparator
        )

    @staticmethod
    def _to_list(
        values: Iterable[Any] | None,
        field_name: str,
    ) -> list[Any]:
        """
        Converte uma coleção em lista.
        """

        if values is None:
            return []

        if isinstance(
            values,
            (str, bytes),
        ):
            raise TypeError(
                f"{field_name} não pode ser uma string."
            )

        try:
            return list(values)

        except TypeError as exc:
            raise TypeError(
                f"{field_name} deve ser uma coleção iterável."
            ) from exc

    def compare(
        self,
        markets: Iterable[Any] | None,
    ) -> list[Any]:
        """
        Compara mercados entre plataformas.

        Uma comparação de arbitragem normalmente
        necessita de pelo menos dois mercados.
        """

        market_list = self._to_list(
            markets,
            "markets",
        )

        if len(market_list) < 2:
            return []

        opportunities = self._comparator.compare(
            market_list,
        )

        return self._to_list(
            opportunities,
            "opportunities",
        )


comparator_service = ComparatorService()