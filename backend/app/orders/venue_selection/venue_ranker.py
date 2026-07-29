from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.venue_selection.venue import Venue
from app.orders.venue_selection.venue_score import VenueScore, venue_score


class VenueRanker:
    def __init__(self, *, scorer: VenueScore | None = None) -> None:
        self.scorer = scorer if scorer is not None else venue_score
        self.last_ranking: list[dict[str, Any]] = []

    def rank(self, venues: Iterable[Any], order: Any = None) -> list[Venue]:
        resolved = [Venue.from_value(venue) for venue in venues]
        for venue in resolved:
            venue.score = self.scorer.calculate(venue, order)

        ranked = sorted(
            resolved,
            key=lambda venue: (
                -venue.score,
                venue.latency,
                venue.fee,
                venue.name.lower(),
            ),
        )
        self.last_ranking = [venue.to_dict() for venue in ranked]
        return ranked


venue_ranker = VenueRanker()
