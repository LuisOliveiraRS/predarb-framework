from __future__ import annotations

from typing import Any

from app.market.comparators.cross_platform import (
    CrossPlatformComparator,
)


class ArbitrageStage:
    """
    Estágio independente para comparação
    de mercados.

    Este estágio não depende do ArbitrageEngine,
    evitando dependência circular.

    Entrada:
        lista de mercados.

    Saída:
        lista de oportunidades.
    """

    def __init__(self) -> None:
        self.comparator = CrossPlatformComparator()

    def execute(
        self,
        markets: list[Any],
    ) -> list[Any]:
        if not markets:
            return []

        opportunities = self.comparator.compare(
            markets,
        )

        if opportunities is None:
            return []

        return list(opportunities)