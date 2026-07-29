from __future__ import annotations

from typing import Any

from app.orders.ai_router.execution_history import ExecutionHistory, execution_history
from app.orders.ai_router.router_dataset import RouterDataset
from app.orders.ai_router.router_feature_builder import (
    RouterFeatureBuilder,
    router_feature_builder,
)


class RouterStatistics:
    """Resumo explicável do histórico usado pelo roteamento adaptativo."""

    def __init__(
        self,
        *,
        history: ExecutionHistory | None = None,
        feature_builder: RouterFeatureBuilder | None = None,
    ) -> None:
        self.history = history if history is not None else execution_history
        if feature_builder is not None:
            self.feature_builder = feature_builder
        elif history is not None:
            self.feature_builder = RouterFeatureBuilder(
                dataset=RouterDataset(history=self.history)
            )
        else:
            self.feature_builder = router_feature_builder
        self.last_report: dict[str, Any] = {}

    def summary(self) -> dict[str, Any]:
        features = self.feature_builder.build()
        venues = {
            name: {
                "orders": int(feature["samples"]),
                "samples": int(feature["samples"]),
                "success": feature["success_rate"],
                "success_rate": feature["success_rate"],
                "recent_success_rate": feature["recent_success_rate"],
                "latency": feature["average_latency_ms"],
                "average_latency_ms": feature["average_latency_ms"],
                "slippage": feature["average_slippage_rate"],
                "average_slippage_rate": feature["average_slippage_rate"],
                "fee": feature["average_fee_rate"],
                "average_fee_rate": feature["average_fee_rate"],
                "quantity": feature["total_quantity"],
                "confidence": feature["confidence"],
            }
            for name, feature in features.items()
        }
        report = {
            "total_orders": self.history.total_reports(),
            "total_reports": self.history.total_reports(),
            "venues": venues,
            "learned_venues": sum(1 for item in venues.values() if item["samples"] > 0),
            "live_execution": False,
        }
        self.last_report = report
        return report

    snapshot = summary


router_statistics = RouterStatistics()
