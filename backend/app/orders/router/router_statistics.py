from __future__ import annotations

from typing import Any

from app.orders.router.router_metrics import RouterMetrics, router_metrics


class RouterStatistics:
    def __init__(self, *, metrics: RouterMetrics | None = None) -> None:
        self.metrics = metrics if metrics is not None else router_metrics

    def summary(self) -> dict[str, Any]:
        data = self.metrics.snapshot()
        count = data["routes_used"]
        return {
            "routes": count,
            "average_latency": round(data["total_latency"] / count, 8) if count else 0.0,
            "average_fee": round(data["total_fee"] / count, 8) if count else 0.0,
            "average_score": round(data["total_score"] / count, 8) if count else 0.0,
            "fees": data["total_fee"],
            "by_exchange": data["by_exchange"],
        }


router_statistics = RouterStatistics()
