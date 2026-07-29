from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable, Mapping
from statistics import mean
from typing import Any

from app.orders.ai_router.router_dataset import RouterDataset, router_dataset


class RouterFeatureBuilder:
    """Constrói features agregadas por venue a partir do dataset normalizado."""

    def __init__(
        self,
        *,
        dataset: RouterDataset | None = None,
        confidence_samples: int = 20,
        recent_window: int = 20,
    ) -> None:
        self.dataset = dataset if dataset is not None else router_dataset
        self.confidence_samples = max(1, int(confidence_samples))
        self.recent_window = max(1, int(recent_window))
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _weighted_mean(rows: list[dict[str, Any]], field_name: str) -> float:
        weights = [max(float(row.get("executed_quantity", 0.0)), 1.0) for row in rows]
        total_weight = sum(weights)
        if total_weight <= 0:
            return 0.0
        return sum(float(row.get(field_name, 0.0)) * weight for row, weight in zip(rows, weights)) / total_weight

    def build(
        self,
        rows: Iterable[Mapping[str, Any]] | None = None,
    ) -> dict[str, dict[str, Any]]:
        dataset_rows = [dict(row) for row in rows] if rows is not None else self.dataset.build()
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        display_names: dict[str, str] = {}

        for row in dataset_rows:
            venue = str(row.get("venue", "")).strip()
            if not venue:
                continue
            key = venue.casefold()
            display_names.setdefault(key, venue)
            grouped[key].append(row)

        features: dict[str, dict[str, Any]] = {}
        for key, venue_rows in grouped.items():
            samples = len(venue_rows)
            recent_rows = venue_rows[-self.recent_window :]
            success_rate = mean(float(bool(row.get("success"))) for row in venue_rows)
            recent_success_rate = mean(
                float(bool(row.get("success"))) for row in recent_rows
            )
            latency_ms = self._weighted_mean(venue_rows, "latency_ms")
            slippage_rate = self._weighted_mean(venue_rows, "slippage_rate")
            fee_rate = self._weighted_mean(venue_rows, "fee_rate")
            total_quantity = sum(float(row.get("executed_quantity", 0.0)) for row in venue_rows)
            total_fees = sum(float(row.get("fee_amount", 0.0)) for row in venue_rows)
            confidence = min(1.0, samples / self.confidence_samples)

            feature = {
                "venue": display_names[key],
                "samples": samples,
                "recent_samples": len(recent_rows),
                "success_rate": round(success_rate, 8),
                "recent_success_rate": round(recent_success_rate, 8),
                "average_latency_ms": round(latency_ms, 8),
                "average_slippage_rate": round(slippage_rate, 10),
                "average_fee_rate": round(fee_rate, 10),
                "total_quantity": round(total_quantity, 8),
                "total_fees": round(total_fees, 8),
                "confidence": round(confidence, 8),
                # aliases legados
                "latency": round(latency_ms, 8),
                "slippage": round(slippage_rate, 10),
                "fee": round(fee_rate, 10),
                "success": round(success_rate, 8),
            }
            features[display_names[key]] = feature

        self.last_report = {
            "rows": len(dataset_rows),
            "venues": len(features),
            "confidence_samples": self.confidence_samples,
            "recent_window": self.recent_window,
            "live_execution": False,
        }
        return features

    def for_venue(
        self,
        venue: Any,
        features: Mapping[str, Mapping[str, Any]] | None = None,
    ) -> dict[str, Any]:
        source = dict(features) if features is not None else self.build()
        wanted = str(getattr(venue, "name", venue) or "").strip().casefold()
        for name, feature in source.items():
            if str(name).casefold() == wanted:
                return dict(feature)
        return {
            "venue": str(getattr(venue, "name", venue) or ""),
            "samples": 0,
            "recent_samples": 0,
            "success_rate": 0.0,
            "recent_success_rate": 0.0,
            "average_latency_ms": 0.0,
            "average_slippage_rate": 0.0,
            "average_fee_rate": 0.0,
            "total_quantity": 0.0,
            "total_fees": 0.0,
            "confidence": 0.0,
            "latency": 0.0,
            "slippage": 0.0,
            "fee": 0.0,
            "success": 0.0,
        }


router_feature_builder = RouterFeatureBuilder()
