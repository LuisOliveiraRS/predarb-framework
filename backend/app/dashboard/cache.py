from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from threading import RLock
from typing import Any


class DashboardCache:
    """Cache thread-safe dos snapshots serializados do Dashboard."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._data: dict[str, Any] = {}
        self._updated_at: datetime | None = None
        self._version = 0

    @staticmethod
    def _copy(value: Any) -> Any:
        try:
            return deepcopy(value)
        except Exception:
            return value

    def set(self, key: str, value: Any) -> Any:
        normalized = str(key or "").strip()
        if not normalized:
            raise ValueError("key não pode ser vazia.")

        with self._lock:
            self._data[normalized] = self._copy(value)
            self._updated_at = datetime.now(timezone.utc)
            self._version += 1

        return value

    def get(self, key: str, default: Any = None) -> Any:
        normalized = str(key or "").strip()
        if not normalized:
            return self._copy(default)

        with self._lock:
            return self._copy(self._data.get(normalized, default))

    def update(self, data: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(data, dict):
            raise TypeError("data deve ser um dicionário.")

        with self._lock:
            self._data.update(self._copy(data))
            self._updated_at = datetime.now(timezone.utc)
            self._version += 1

        return data

    def clear(self) -> None:
        with self._lock:
            self._data.clear()
            self._updated_at = datetime.now(timezone.utc)
            self._version += 1

    reset = clear

    def all(self) -> dict[str, Any]:
        with self._lock:
            return self._copy(self._data)

    snapshot = all

    @property
    def updated_at(self) -> datetime | None:
        with self._lock:
            return self._updated_at

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "keys": sorted(self._data),
                "size": len(self._data),
                "version": self._version,
                "updated_at": (
                    self._updated_at.isoformat()
                    if self._updated_at is not None
                    else None
                ),
            }


dashboard_cache = DashboardCache()
