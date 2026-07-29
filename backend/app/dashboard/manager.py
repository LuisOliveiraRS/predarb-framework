from __future__ import annotations

from typing import Any

from app.dashboard.dashboard_service import DashboardService, dashboard_service


class DashboardManager:
    """Fachada de consulta do Dashboard."""

    def __init__(self, service: DashboardService | None = None) -> None:
        self.service = service or dashboard_service

    def snapshot(self, *, refresh: bool = True) -> dict[str, Any]:
        return self.service.snapshot(refresh=refresh)

    def status(self) -> dict[str, Any]:
        snapshot = self.snapshot()
        return {
            "system": snapshot["status"],
            "markets": snapshot["markets"],
            "opportunities": snapshot["opportunities"],
            "orders": snapshot["orders"],
            "positions": snapshot["positions"],
            "connections": snapshot["connections"],
            "portfolio": snapshot["portfolio"],
            "pnl": snapshot["pnl"],
            "ai_confidence": snapshot["ai_confidence"],
            "updated_at": snapshot["updated_at"],
        }

    def events(self, limit: int | None = None) -> list[dict[str, Any]]:
        return self.service.latest_events(limit)

    def clear_cache(self) -> None:
        self.service.cache.clear()


dashboard_manager = DashboardManager()
