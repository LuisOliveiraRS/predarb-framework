from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.venue_selection.venue import Venue
from app.orders.venue_selection.venue_ranker import VenueRanker, venue_ranker
from app.orders.venue_selection.venue_repository import VenueRepository, venue_repository


class SmartVenueSelector:
    """Filtra e ordena venues; não envia ordens."""

    def __init__(
        self,
        *,
        repository: VenueRepository | None = None,
        ranker: VenueRanker | None = None,
    ) -> None:
        self.repository = repository if repository is not None else venue_repository
        self.ranker = ranker if ranker is not None else venue_ranker
        self.last_report: dict[str, Any] = {}

    def select(
        self,
        order: Any,
        venues: Iterable[Any] | None = None,
        *,
        min_reliability: float = 0.0,
        max_latency: float | None = None,
        max_fee: float | None = None,
        require_liquidity: bool = True,
        require_full_liquidity: bool = False,
    ) -> list[Venue]:
        candidates = list(venues) if venues is not None else self.repository.all()
        required_quantity = float(
            getattr(order, "remaining_quantity", getattr(order, "quantity", 0.0))
            or 0.0
        )
        eligible: list[Venue] = []
        rejected: list[dict[str, Any]] = []

        for item in candidates:
            venue = Venue.from_value(item)
            reasons: list[str] = []
            reliability = venue.reliability * 100 if venue.reliability <= 1 else venue.reliability
            minimum = min_reliability * 100 if min_reliability <= 1 else min_reliability

            if not venue.available:
                reasons.append("VENUE_DISABLED")
            if reliability < minimum:
                reasons.append("RELIABILITY_LOW")
            if max_latency is not None and venue.latency > float(max_latency):
                reasons.append("LATENCY_LIMIT_EXCEEDED")
            if max_fee is not None and venue.fee > float(max_fee):
                reasons.append("FEE_LIMIT_EXCEEDED")
            if require_liquidity and venue.liquidity <= 0:
                reasons.append("LIQUIDITY_MISSING")
            if require_full_liquidity and venue.liquidity < required_quantity:
                reasons.append("INSUFFICIENT_FULL_LIQUIDITY")

            if reasons:
                rejected.append({"venue": venue.name, "reasons": reasons})
            else:
                eligible.append(venue)

        ranked = self.ranker.rank(eligible, order)
        self.last_report = {
            "candidates": len(candidates),
            "eligible": len(ranked),
            "rejected": rejected,
            "ranking": [venue.to_dict() for venue in ranked],
        }
        return ranked


smart_venue_selector = SmartVenueSelector()
