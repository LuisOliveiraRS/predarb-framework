from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from math import isfinite
from statistics import mean
from typing import Any

from app.orders.ai_router.execution_history import (
    ExecutionHistory,
    execution_history,
)
from app.orders.ai_router.router_dataset import RouterDataset
from app.orders.ai_router.router_feature_builder import RouterFeatureBuilder
from app.orders.ai_router.venue_learning import VenueLearning, venue_learning


class RouterMetrics:
    """Métricas JSON-safe do roteamento adaptativo.

    A fonte oficial é o ``ExecutionHistory`` consolidado pelo OMS. Os relatórios
    podem ser dicionários ou objetos; a normalização é delegada ao
    ``RouterDataset`` para manter as mesmas unidades usadas pelo AI Router.
    """

    def __init__(
        self,
        *,
        history: ExecutionHistory | None = None,
        dataset: RouterDataset | None = None,
        feature_builder: RouterFeatureBuilder | None = None,
        learning: VenueLearning | None = None,
    ) -> None:
        if history is not None:
            self.history = history
        elif dataset is not None and hasattr(dataset, "history"):
            self.history = dataset.history
        elif (
            feature_builder is not None
            and hasattr(feature_builder, "dataset")
            and hasattr(feature_builder.dataset, "history")
        ):
            self.history = feature_builder.dataset.history
        else:
            self.history = execution_history

        if dataset is not None:
            self.dataset = dataset
        elif feature_builder is not None and hasattr(feature_builder, "dataset"):
            self.dataset = feature_builder.dataset
        else:
            self.dataset = RouterDataset(history=self.history)

        self.feature_builder = feature_builder or RouterFeatureBuilder(
            dataset=self.dataset
        )
        self.learning = learning or venue_learning
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return float(default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if isfinite(number) else float(default)

    @classmethod
    def _weighted_mean(
        cls,
        rows: list[Mapping[str, Any]],
        field_name: str,
        *,
        quantity_weighted: bool = True,
    ) -> float:
        if not rows:
            return 0.0

        if quantity_weighted:
            weights = [
                max(cls._number(row.get("executed_quantity")), 1.0)
                for row in rows
            ]
        else:
            weights = [1.0 for _ in rows]

        total_weight = sum(weights)
        if total_weight <= 0:
            return 0.0

        return sum(
            cls._number(row.get(field_name)) * weight
            for row, weight in zip(rows, weights)
        ) / total_weight

    @classmethod
    def _average_price(cls, rows: list[Mapping[str, Any]]) -> float:
        total_quantity = sum(
            max(cls._number(row.get("executed_quantity")), 0.0)
            for row in rows
        )
        if total_quantity <= 0:
            return 0.0

        return sum(
            cls._number(row.get("average_price"))
            * max(cls._number(row.get("executed_quantity")), 0.0)
            for row in rows
        ) / total_quantity

    def build(
        self,
        history: Mapping[str, list[Any]] | None = None,
    ) -> dict[str, Any]:
        rows = self.dataset.build(history)
        features = self.feature_builder.build(rows)

        venue_metrics: dict[str, dict[str, Any]] = {}
        for venue_name, feature in sorted(
            features.items(),
            key=lambda item: item[0].casefold(),
        ):
            learning_details = self.learning.details(feature)
            venue_metrics[venue_name] = {
                "orders": int(feature["samples"]),
                "samples": int(feature["samples"]),
                "recent_samples": int(feature["recent_samples"]),
                "success": feature["success_rate"],
                "success_rate": feature["success_rate"],
                "success_rate_percentage": round(
                    feature["success_rate"] * 100.0,
                    2,
                ),
                "recent_success_rate": feature["recent_success_rate"],
                "latency": feature["average_latency_ms"],
                "average_latency": feature["average_latency_ms"],
                "average_latency_ms": feature["average_latency_ms"],
                "slippage": feature["average_slippage_rate"],
                "average_slippage": feature["average_slippage_rate"],
                "average_slippage_rate": feature[
                    "average_slippage_rate"
                ],
                "fee": feature["average_fee_rate"],
                "average_fee_rate": feature["average_fee_rate"],
                "quantity": feature["total_quantity"],
                "total_quantity": feature["total_quantity"],
                "total_fees": feature["total_fees"],
                "confidence": feature["confidence"],
                "learning_score": learning_details["score"],
            }

        total_reports = len(rows)
        recorded_reports = self.history.total_reports()
        rejected = list(self.dataset.last_report.get("rejected", []))
        status = (
            "DEGRADED"
            if rejected or (recorded_reports > 0 and total_reports == 0)
            else "ONLINE"
        )

        success_rate = (
            mean(float(bool(row.get("success"))) for row in rows)
            if rows
            else 0.0
        )
        total_quantity = sum(
            max(self._number(row.get("executed_quantity")), 0.0)
            for row in rows
        )
        total_fees = sum(
            max(self._number(row.get("fee_amount")), 0.0)
            for row in rows
        )
        total_notional = sum(
            max(self._number(row.get("executed_notional")), 0.0)
            for row in rows
        )

        confidence_values = [
            self._number(feature.get("confidence"))
            for feature in features.values()
        ]
        average_confidence = (
            mean(confidence_values)
            if confidence_values
            else 0.0
        )

        summary = {
            "orders": total_reports,
            "reports": total_reports,
            "recorded_reports": recorded_reports,
            "venues": len(venue_metrics),
            "learned_venues": sum(
                1
                for item in venue_metrics.values()
                if item["samples"] > 0
            ),
            "average_latency": round(
                self._weighted_mean(rows, "latency_ms"),
                8,
            ),
            "average_latency_ms": round(
                self._weighted_mean(rows, "latency_ms"),
                8,
            ),
            "average_slippage": round(
                self._weighted_mean(rows, "slippage_rate"),
                10,
            ),
            "average_slippage_rate": round(
                self._weighted_mean(rows, "slippage_rate"),
                10,
            ),
            "average_fee_rate": round(
                self._weighted_mean(rows, "fee_rate"),
                10,
            ),
            "average_price": round(self._average_price(rows), 8),
            "success_rate": round(success_rate, 8),
            "success_rate_percentage": round(success_rate * 100.0, 2),
            "total_quantity": round(total_quantity, 8),
            "total_fees": round(total_fees, 8),
            "total_notional": round(total_notional, 8),
            "confidence": round(average_confidence, 8),
            "average_confidence": round(average_confidence, 8),
            "live_execution": False,
        }

        report = {
            "status": status,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "venues": venue_metrics,
            "diagnostics": {
                "dataset": dict(self.dataset.last_report),
                "features": dict(self.feature_builder.last_report),
                "rejected": rejected,
            },
        }
        self.last_report = report
        return report

    snapshot = build

    def summary(self) -> dict[str, Any]:
        return dict(self.build()["summary"])

    def venues(self) -> dict[str, dict[str, Any]]:
        return dict(self.build()["venues"])

    def status(self) -> dict[str, Any]:
        return {
            "history": self.history.status(),
            "last_report": dict(self.last_report),
            "live_execution": False,
        }


router_metrics = RouterMetrics()
