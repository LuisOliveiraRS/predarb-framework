from __future__ import annotations

from collections.abc import Callable
from typing import Any

from app.events.event_registry import EventRegistry, event_registry


class EventBus:
    """Publica eventos para handlers registrados.

    Instâncias criadas diretamente recebem um registro isolado. O singleton
    ``event_bus`` utiliza o registro global oficial.
    """

    def __init__(self, registry: EventRegistry | None = None) -> None:
        self.registry = registry or EventRegistry()

    def publish(self, event: Any) -> list[Any]:
        if event is None:
            raise ValueError("Não é possível publicar um evento None.")

        event_name = getattr(event, "name", None)
        if not isinstance(event_name, str) or not event_name.strip():
            raise TypeError("O evento deve possuir um nome válido.")

        results: list[Any] = []
        for callback in self.registry.listeners(event_name):
            results.append(callback(event))
        return results

    def subscribe(
        self,
        event_name: str,
        callback: Callable[[Any], Any],
    ) -> bool:
        return self.registry.subscribe(event_name, callback)

    def unsubscribe(
        self,
        event_name: str,
        callback: Callable[[Any], Any],
    ) -> bool:
        return self.registry.unsubscribe(event_name, callback)

    def listeners(self, event_name: str) -> list[Callable[[Any], Any]]:
        return self.registry.listeners(event_name)

    def status(self) -> dict[str, Any]:
        return self.registry.status()


event_bus = EventBus(event_registry)
