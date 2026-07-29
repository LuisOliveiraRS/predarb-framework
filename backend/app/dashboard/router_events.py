from __future__ import annotations

import asyncio
import inspect
from typing import Any

from app.dashboard.router_dashboard import RouterDashboard, router_dashboard
from app.events.event import Event
from app.events.event_bus import event_bus


class RouterEvents:
    """Publica snapshots do AI Router no EventBus oficial."""

    EVENT_NAME = "router.dashboard.updated"

    def __init__(
        self,
        *,
        dashboard: RouterDashboard | None = None,
        bus: Any = None,
    ) -> None:
        self.dashboard = dashboard or router_dashboard
        self.bus = bus or event_bus
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _schedule(result: Any) -> bool:
        if not inspect.isawaitable(result):
            return False

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return False

        loop.create_task(result)
        return True

    def publish(self, *, refresh: bool = True) -> dict[str, Any]:
        payload = self.dashboard.snapshot(refresh=refresh)
        event = Event(self.EVENT_NAME, payload)
        result = self.bus.publish(event)
        scheduled = self._schedule(result)

        self.last_report = {
            "event": self.EVENT_NAME,
            "published": True,
            "async_scheduled": scheduled,
            "updated_at": payload.get("updated_at"),
        }
        return payload

    def status(self) -> dict[str, Any]:
        return dict(self.last_report)


router_events = RouterEvents()
