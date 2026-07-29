from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from app.orders.venue_selection.venue import Venue


class VenueRepository:
    def __init__(self, venues: Iterable[Any] | None = None) -> None:
        self._venues: dict[str, Venue] = {}
        self._lock = RLock()
        if venues is not None:
            self.add_many(venues)

    def add(self, venue: Any, *, replace: bool = True) -> Venue:
        resolved = Venue.from_value(venue)
        key = resolved.name.casefold()
        with self._lock:
            if key in self._venues and not replace:
                raise ValueError(f"Venue já registrada: {resolved.name}.")
            self._venues[key] = resolved
        return resolved

    def add_many(self, venues: Iterable[Any], *, replace: bool = True) -> list[Venue]:
        return [self.add(venue, replace=replace) for venue in venues]

    def remove(self, venue_name: Any) -> Venue | None:
        with self._lock:
            return self._venues.pop(str(venue_name or "").strip().casefold(), None)

    def get(self, venue_name: Any, default: Any = None) -> Venue | Any:
        with self._lock:
            return self._venues.get(
                str(venue_name or "").strip().casefold(),
                default,
            )

    def all(self) -> list[Venue]:
        with self._lock:
            return list(self._venues.values())

    list = all

    def enabled(self) -> list[Venue]:
        return [venue for venue in self.all() if venue.available]

    def count(self) -> int:
        with self._lock:
            return len(self._venues)

    def clear(self) -> None:
        with self._lock:
            self._venues.clear()


venue_repository = VenueRepository()
