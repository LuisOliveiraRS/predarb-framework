from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any


class RouterCache:
    """Cache thread-safe do snapshot do AI Router Dashboard."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._snapshot: dict[str, Any] = {}
        self._last_update: datetime | None = None
        self._version = 0

    @staticmethod
    def _copy(value: Any) -> Any:
        try:
            return deepcopy(value)
        except Exception:
            return value

    def update(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(snapshot, dict):
            raise TypeError("snapshot deve ser um dicionário.")

        with self._lock:
            self._snapshot = self._copy(snapshot)
            self._last_update = datetime.now(timezone.utc)
            self._version += 1

        return snapshot

    set = update

    def data(self) -> dict[str, Any]:
        with self._lock:
            return self._copy(self._snapshot)

    snapshot = data

    def get(self) -> dict[str, Any]:
        """Interface legada que retorna metadados e o snapshot."""

        with self._lock:
            updated_at = (
                self._last_update.isoformat()
                if self._last_update is not None
                else None
            )
            return {
                "last_update": updated_at,
                "updated_at": updated_at,
                "version": self._version,
                "data": self._copy(self._snapshot),
            }

    def clear(self) -> None:
        with self._lock:
            self._snapshot = {}
            self._last_update = datetime.now(timezone.utc)
            self._version += 1

    reset = clear

    @property
    def last_update(self) -> datetime | None:
        with self._lock:
            return self._last_update

    @property
    def updated_at(self) -> datetime | None:
        return self.last_update

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    @property
    def empty(self) -> bool:
        with self._lock:
            return not bool(self._snapshot)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "empty": not bool(self._snapshot),
                "version": self._version,
                "updated_at": (
                    self._last_update.isoformat()
                    if self._last_update is not None
                    else None
                ),
                "keys": sorted(self._snapshot),
            }


router_cache = RouterCache()
