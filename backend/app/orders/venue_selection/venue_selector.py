from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.venue_selection.venue import Venue
from app.orders.venue_selection.venue_ranker import VenueRanker, venue_ranker
from app.orders.venue_selection.venue_repository import VenueRepository, venue_repository


class VenueSelector:
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
        order: Any = None,
        venues: Iterable[Any] | None = None,
    ) -> Venue | None:
        candidates = list(venues) if venues is not None else self.repository.enabled()
        available = [Venue.from_value(item) for item in candidates]
        available = [venue for venue in available if venue.available]
        ranked = self.ranker.rank(available, order)
        selected = ranked[0] if ranked else None
        self.last_report = {
            "candidates": len(candidates),
            "eligible": len(ranked),
            "selected": selected.name if selected else None,
            "ranking": [venue.to_dict() for venue in ranked],
        }
        return selected


venue_selector = VenueSelector()
