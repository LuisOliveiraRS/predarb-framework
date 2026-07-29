from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.ai_router.route_score import RouteScore, route_score
from app.orders.ai_router.router_feature_builder import (
    RouterFeatureBuilder,
    router_feature_builder,
)
from app.orders.venue_selection.venue import Venue


class RoutePredictor:
    """Rankeador adaptativo determinístico e explicável."""

    def __init__(
        self,
        *,
        feature_builder: RouterFeatureBuilder | None = None,
        scorer: RouteScore | None = None,
    ) -> None:
        self.feature_builder = feature_builder if feature_builder is not None else router_feature_builder
        self.scorer = scorer if scorer is not None else route_score
        self.last_report: dict[str, Any] = {}

    def predict(
        self,
        venues: Iterable[Any],
        order: Any = None,
        *,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> list[tuple[float, Venue]]:
        candidates = [Venue.from_value(venue) for venue in venues]
        feature_map = dict(features) if features is not None else self.feature_builder.build()
        ranking: list[tuple[float, Venue]] = []
        details: list[dict[str, Any]] = []

        for venue in candidates:
            venue_features = self.feature_builder.for_venue(venue, feature_map)
            score_details = self.scorer.details(venue, venue_features, order)
            ranking.append((score_details["score"], venue))
            details.append({**score_details, "features": venue_features})

        ranking.sort(
            key=lambda item: (
                -item[0],
                item[1].latency,
                item[1].fee,
                item[1].name.casefold(),
            )
        )
        detail_by_name = {item["venue"].casefold(): item for item in details}
        self.last_report = {
            "venues": len(candidates),
            "ranking": [
                detail_by_name[venue.name.casefold()] for _, venue in ranking
            ],
            "selected": ranking[0][1].name if ranking else None,
            "live_execution": False,
        }
        return ranking

    rank = predict


route_predictor = RoutePredictor()
