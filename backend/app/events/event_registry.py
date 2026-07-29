from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Any


class EventRegistry:
    """Registro thread-safe e idempotente de handlers de eventos."""

    def __init__(self) -> None:
        self.handlers: dict[str, list[Callable[[Any], Any]]] = {}
        self._lock = RLock()

    @staticmethod
    def _event_name(event_name: str) -> str:
        if not isinstance(event_name, str):
            raise TypeError("O nome do evento deve ser uma string.")
        normalized = event_name.strip()
        if not normalized:
            raise ValueError("O nome do evento não pode ser vazio.")
        return normalized

    def subscribe(
        self,
        event_name: str,
        callback: Callable[[Any], Any],
    ) -> bool:
        normalized = self._event_name(event_name)
        if not callable(callback):
            raise TypeError("O callback do evento deve ser executável.")

        with self._lock:
            listeners = self.handlers.setdefault(normalized, [])
            if callback in listeners:
                return False
            listeners.append(callback)
            return True

    def unsubscribe(
        self,
        event_name: str,
        callback: Callable[[Any], Any],
    ) -> bool:
        normalized = self._event_name(event_name)
        with self._lock:
            listeners = self.handlers.get(normalized)
            if not listeners or callback not in listeners:
                return False
            listeners.remove(callback)
            if not listeners:
                self.handlers.pop(normalized, None)
            return True

    def listeners(self, event_name: str) -> list[Callable[[Any], Any]]:
        normalized = self._event_name(event_name)
        with self._lock:
            return list(self.handlers.get(normalized, ()))

    def clear(self, event_name: str | None = None) -> int:
        with self._lock:
            if event_name is None:
                count = sum(len(items) for items in self.handlers.values())
                self.handlers.clear()
                return count

            normalized = self._event_name(event_name)
            return len(self.handlers.pop(normalized, ()))

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "events": len(self.handlers),
                "listeners": sum(len(items) for items in self.handlers.values()),
                "subscriptions": {
                    name: len(items)
                    for name, items in sorted(self.handlers.items())
                },
            }


event_registry = EventRegistry()
