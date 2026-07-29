from __future__ import annotations

from typing import Any

from app.dashboard.router_cache import RouterCache, router_cache
from app.dashboard.router_metrics import RouterMetrics, router_metrics


class RouterDashboard:
    """Serviço de consulta do Dashboard do AI Router."""

    def __init__(
        self,
        *,
        metrics: RouterMetrics | None = None,
        cache: RouterCache | None = None,
    ) -> None:
        self.metrics = metrics or router_metrics
        self.cache = cache or router_cache
        self.last_report: dict[str, Any] = {}

    def snapshot(self, *, refresh: bool = True) -> dict[str, Any]:
        if not refresh:
            cached = self.cache.data()
            if cached:
                return cached

        snapshot = self.metrics.build()
        self.cache.update(snapshot)
        self.last_report = {
            "status": snapshot.get("status", "UNKNOWN"),
            "updated_at": snapshot.get("updated_at"),
            "orders": snapshot.get("summary", {}).get("orders", 0),
            "venues": len(snapshot.get("venues", {})),
            "cache_version": self.cache.version,
        }
        return snapshot

    refresh = snapshot

    def venue_table(self, *, refresh: bool = True) -> dict[str, Any]:
        return dict(self.snapshot(refresh=refresh).get("venues", {}))

    venues = venue_table

    def summary(self, *, refresh: bool = True) -> dict[str, Any]:
        return dict(self.snapshot(refresh=refresh).get("summary", {}))

    def clear_cache(self) -> None:
        self.cache.clear()

    def status(self) -> dict[str, Any]:
        return {
            "cache": self.cache.status(),
            "metrics": self.metrics.status(),
            "last_report": dict(self.last_report),
            "live_execution": False,
        }


router_dashboard = RouterDashboard()
