from __future__ import annotations

from typing import Any

from app.orders.venue_selection.venue import Venue


class VenueScore:
    """Score determinístico de 0 a 100 para seleção de venue."""

    def __init__(
        self,
        *,
        liquidity_weight: float = 0.40,
        reliability_weight: float = 0.35,
        latency_weight: float = 0.15,
        fee_weight: float = 0.10,
        latency_limit_ms: float = 500.0,
        fee_limit: float = 0.02,
    ) -> None:
        self.liquidity_weight = float(liquidity_weight)
        self.reliability_weight = float(reliability_weight)
        self.latency_weight = float(latency_weight)
        self.fee_weight = float(fee_weight)
        self.latency_limit_ms = max(float(latency_limit_ms), 1e-9)
        self.fee_limit = max(float(fee_limit), 1e-12)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(100.0, float(value)))

    @staticmethod
    def _required_quantity(order: Any) -> float:
        if order is None:
            return 0.0
        value = getattr(order, "remaining_quantity", getattr(order, "quantity", 0.0))
        try:
            return max(0.0, float(value))
        except (TypeError, ValueError):
            return 0.0

    def details(self, venue: Venue | Any, order: Any = None) -> dict[str, float]:
        resolved = Venue.from_value(venue)
        required = self._required_quantity(order)

        liquidity_score = (
            self._clamp((resolved.liquidity / required) * 100)
            if required > 0
            else self._clamp(resolved.liquidity if resolved.liquidity <= 100 else 100)
        )
        reliability_score = self._clamp(
            resolved.reliability * 100
            if resolved.reliability <= 1
            else resolved.reliability
        )
        latency_score = self._clamp(
            100 - (resolved.latency / self.latency_limit_ms) * 100
        )
        fee_score = self._clamp(100 - (resolved.fee / self.fee_limit) * 100)

        score = (
            liquidity_score * self.liquidity_weight
            + reliability_score * self.reliability_weight
            + latency_score * self.latency_weight
            + fee_score * self.fee_weight
        )
        return {
            "score": round(self._clamp(score), 6),
            "liquidity_score": round(liquidity_score, 6),
            "reliability_score": round(reliability_score, 6),
            "latency_score": round(latency_score, 6),
            "fee_score": round(fee_score, 6),
        }

    def calculate(self, venue: Venue | Any, order: Any = None) -> float:
        return self.details(venue, order)["score"]


venue_score = VenueScore()
