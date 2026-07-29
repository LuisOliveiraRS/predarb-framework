from __future__ import annotations

from typing import Any

from app.dashboard.dashboard_service import DashboardService, dashboard_service


class MetricsService:
    def __init__(self, service: DashboardService | None = None) -> None:
        self.service = service or dashboard_service

    def statistics(self) -> dict[str, Any]:
        return self.service.metrics()

    summary = statistics
    snapshot = statistics


metrics_service = MetricsService()
