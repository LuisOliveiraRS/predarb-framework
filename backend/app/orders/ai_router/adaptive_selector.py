from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.ai_router.adaptive_router import AdaptiveRouter, adaptive_router
from app.orders.venue_selection.venue import Venue


class AdaptiveSelector:
    """Camada final de seleção adaptativa; apenas retorna ranking ou venue."""

    def __init__(self, *, router: AdaptiveRouter | None = None) -> None:
        self.router = router if router is not None else adaptive_router
        self.last_report: dict[str, Any] = {}

    def rank(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[tuple[float, Venue]]:
        ranking = self.router.rank(venues, order, features=features)
        self.last_report = dict(self.router.last_report)
        return ranking

    def select(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Venue | None:
        ranking = self.rank(venues, order, features=features)
        return ranking[0][1] if ranking else None


adaptive_selector = AdaptiveSelector()
