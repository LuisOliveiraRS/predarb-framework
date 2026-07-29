from __future__ import annotations

from typing import Any

from app.dashboard.router_cache import RouterCache, router_cache
from app.dashboard.router_dashboard import RouterDashboard, router_dashboard


class RouterPublisher:
    """Produz um snapshot único para API, cache e WebSocket."""

    def __init__(
        self,
        *,
        dashboard: RouterDashboard | None = None,
        cache: RouterCache | None = None,
    ) -> None:
        self.dashboard = dashboard or router_dashboard
        self.cache = cache or router_cache
        self.last_report: dict[str, Any] = {}

    def publish(self, *, refresh: bool = True) -> dict[str, Any]:
        snapshot = self.dashboard.snapshot(refresh=refresh)

        if self.dashboard.cache is not self.cache:
            self.cache.update(snapshot)

        self.last_report = {
            "status": snapshot.get("status", "UNKNOWN"),
            "updated_at": snapshot.get("updated_at"),
            "orders": snapshot.get("summary", {}).get("orders", 0),
            "venues": len(snapshot.get("venues", {})),
            "cache_version": self.cache.version,
        }
        return snapshot

    snapshot = publish

    def status(self) -> dict[str, Any]:
        return {
            "cache": self.cache.status(),
            "last_report": dict(self.last_report),
            "live_execution": False,
        }


router_publisher = RouterPublisher()
