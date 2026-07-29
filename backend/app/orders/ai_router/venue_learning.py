from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class VenueLearning:
    """Transforma desempenho histórico em score de 0 a 100."""

    def __init__(
        self,
        *,
        latency_target_ms: float = 250.0,
        slippage_target: float = 0.01,
        fee_target: float = 0.005,
    ) -> None:
        self.latency_target_ms = max(float(latency_target_ms), 1e-9)
        self.slippage_target = max(float(slippage_target), 1e-12)
        self.fee_target = max(float(fee_target), 1e-12)

    @staticmethod
    def _clamp(value: Any, minimum: float = 0.0, maximum: float = 1.0) -> float:
        try:
            number = float(value)
        except (TypeError, ValueError):
            number = 0.0
        return max(minimum, min(maximum, number))

    @staticmethod
    def _quality(value: float, target: float) -> float:
        return 1.0 / (1.0 + max(0.0, value) / target)

    def details(self, features: Mapping[str, Any] | None) -> dict[str, float]:
        source = dict(features or {})
        samples = max(0, int(source.get("samples", 0) or 0))
        success = self._clamp(source.get("recent_success_rate", source.get("success_rate", source.get("success", 0.0))))
        latency = max(0.0, float(source.get("average_latency_ms", source.get("latency", 0.0)) or 0.0))
        slippage = abs(float(source.get("average_slippage_rate", source.get("slippage", 0.0)) or 0.0))
        fee = max(0.0, float(source.get("average_fee_rate", source.get("fee", 0.0)) or 0.0))
        confidence = self._clamp(source.get("confidence", 0.0))

        latency_quality = self._quality(latency, self.latency_target_ms)
        slippage_quality = self._quality(slippage, self.slippage_target)
        fee_quality = self._quality(fee, self.fee_target)

        score = (
            success * 50.0
            + latency_quality * 20.0
            + slippage_quality * 15.0
            + fee_quality * 10.0
            + confidence * 5.0
        )
        return {
            "score": round(max(0.0, min(100.0, score)), 8),
            "samples": float(samples),
            "success_score": round(success * 100.0, 8),
            "latency_quality": round(latency_quality * 100.0, 8),
            "slippage_quality": round(slippage_quality * 100.0, 8),
            "fee_quality": round(fee_quality * 100.0, 8),
            "confidence": round(confidence, 8),
        }

    def score(self, features: Mapping[str, Any] | list[Any]) -> float:
        if isinstance(features, Mapping):
            return self.details(features)["score"]

        reports = list(features)
        if not reports:
            return 0.0
        successes = [float(bool(getattr(report, "success", False))) for report in reports]
        latencies = [float(getattr(report, "execution_time", 0.0) or 0.0) * 1000.0 for report in reports]
        slippages = [float(getattr(report, "slippage", 0.0) or 0.0) for report in reports]
        fees = [float(getattr(report, "fee", 0.0) or 0.0) for report in reports]
        feature = {
            "samples": len(reports),
            "success_rate": sum(successes) / len(reports),
            "recent_success_rate": sum(successes) / len(reports),
            "average_latency_ms": sum(latencies) / len(reports),
            "average_slippage_rate": sum(slippages) / len(reports),
            "average_fee_rate": sum(fees) / len(reports),
            "confidence": 1.0,
        }
        return self.details(feature)["score"]


venue_learning = VenueLearning()
