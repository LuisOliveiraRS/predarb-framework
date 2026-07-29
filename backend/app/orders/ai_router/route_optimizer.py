from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.ai_router.route_predictor import RoutePredictor, route_predictor
from app.orders.venue_selection.venue import Venue


class RouteOptimizer:
    """Seleciona a primeira venue do ranking adaptativo; não envia ordens."""

    def __init__(self, *, predictor: RoutePredictor | None = None) -> None:
        self.predictor = predictor if predictor is not None else route_predictor
        self.last_report: dict[str, Any] = {}

    def rank(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[tuple[float, Venue]]:
        ranking = self.predictor.predict(venues, order, features=features)
        self.last_report = dict(self.predictor.last_report)
        return ranking

    def optimize(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> Venue | None:
        ranking = self.rank(venues, order, features=features)
        return ranking[0][1] if ranking else None

    select = optimize


route_optimizer = RouteOptimizer()
