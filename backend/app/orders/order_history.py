from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, Mapping


class OrderHistory:
    """Registro cronológico thread-safe dos eventos do OMS."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []
        self._lock = RLock()

    @staticmethod
    def _event_value(event: Any) -> str:
        if isinstance(event, Enum):
            event = event.value
        normalized = str(event or "").strip()
        if not normalized:
            raise ValueError("event não pode ser vazio.")
        return normalized

    def add(
        self,
        order_id: Any,
        event: Any,
        *,
        details: Mapping[str, Any] | None = None,
        timestamp: datetime | None = None,
        **extra: Any,
    ) -> dict[str, Any]:
        normalized_id = str(order_id or "").strip()
        if not normalized_id:
            raise ValueError("order_id não pode ser vazio.")

        occurred_at = timestamp or datetime.now(timezone.utc)
        if occurred_at.tzinfo is None:
            occurred_at = occurred_at.replace(tzinfo=timezone.utc)

        payload = dict(details or {})
        payload.update(extra)

        record = {
            "order": normalized_id,
            "order_id": normalized_id,
            "event": self._event_value(event),
            "timestamp": occurred_at,
            "details": payload,
        }

        with self._lock:
            self.events.append(record)

        return deepcopy(record)

    record = add

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(self.events)

    def by_order(self, order_id: Any) -> list[dict[str, Any]]:
        normalized = str(order_id or "").strip()
        if not normalized:
            return []
        return [
            event
            for event in self.all()
            if event["order_id"] == normalized
        ]

    def latest(self, order_id: Any | None = None) -> dict[str, Any] | None:
        events = self.by_order(order_id) if order_id is not None else self.all()
        return events[-1] if events else None

    def count(self, order_id: Any | None = None) -> int:
        return len(self.by_order(order_id)) if order_id is not None else len(self.all())

    def clear(self, order_id: Any | None = None) -> None:
        with self._lock:
            if order_id is None:
                self.events.clear()
                return

            normalized = str(order_id or "").strip()
            self.events[:] = [
                event
                for event in self.events
                if event["order_id"] != normalized
            ]


order_history = OrderHistory()
