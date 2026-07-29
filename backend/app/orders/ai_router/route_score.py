from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.orders.ai_router.venue_learning import VenueLearning, venue_learning
from app.orders.venue_selection.venue import Venue
from app.orders.venue_selection.venue_score import VenueScore, venue_score


class RouteScore:
    """Combina score determinístico e histórico sem ocultar o cold start."""

    def __init__(
        self,
        *,
        learner: VenueLearning | None = None,
        baseline: VenueScore | None = None,
        max_learning_weight: float = 0.60,
    ) -> None:
        self.learner = learner if learner is not None else venue_learning
        self.baseline = baseline if baseline is not None else venue_score
        self.max_learning_weight = max(0.0, min(1.0, float(max_learning_weight)))

    def details(
        self,
        venue: Venue | Any,
        features: Mapping[str, Any] | None = None,
        order: Any = None,
    ) -> dict[str, Any]:
        resolved = Venue.from_value(venue)
        deterministic = (
            float(resolved.score)
            if resolved.score > 0
            else self.baseline.calculate(resolved, order)
        )
        learning = self.learner.details(features or {})
        confidence = max(0.0, min(1.0, float(learning["confidence"])))
        learning_weight = self.max_learning_weight * confidence
        deterministic_weight = 1.0 - learning_weight
        final_score = deterministic * deterministic_weight + learning["score"] * learning_weight

        return {
            "venue": resolved.name,
            "score": round(max(0.0, min(100.0, final_score)), 8),
            "deterministic_score": round(deterministic, 8),
            "learned_score": learning["score"],
            "confidence": round(confidence, 8),
            "deterministic_weight": round(deterministic_weight, 8),
            "learning_weight": round(learning_weight, 8),
            "samples": int(learning["samples"]),
            "cold_start": int(learning["samples"]) == 0,
            "learning": learning,
        }

    def calculate(
        self,
        venue: Venue | Any,
        features: Mapping[str, Any] | None = None,
        order: Any = None,
    ) -> float:
        return self.details(venue, features, order)["score"]


route_score = RouteScore()
