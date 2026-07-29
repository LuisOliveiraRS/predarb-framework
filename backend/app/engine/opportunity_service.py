from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.services.comparator_service import (
    ComparatorService,
    comparator_service,
)


class OpportunityService:
    """
    Fachada legada da Engine para o
    ComparatorService oficial.

    Novos módulos devem preferir:

        app.services.opportunity_service
    """

    def __init__(
        self,
        *,
        comparator: ComparatorService | None = None,
    ) -> None:
        self.comparator = (
            comparator
            or comparator_service
        )

    def compare(
        self,
        markets: Iterable[Any] | None,
    ) -> list[Any]:
        return self.comparator.compare(
            markets
        )

    def generate(
        self,
        markets: Iterable[Any] | None,
    ) -> list[Any]:
        return self.compare(
            markets
        )


opportunity_service = OpportunityService()