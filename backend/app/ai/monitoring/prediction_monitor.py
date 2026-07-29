from __future__ import annotations

from collections import Counter, deque
from collections.abc import Iterable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite
from statistics import mean
from threading import RLock
from typing import Any


class PredictionMonitor:
    """
    Histórico leve e thread-safe das análises consultivas da camada AI.

    O monitor armazena somente metadados resumidos da inferência. Ele não
    persiste ordens, não altera oportunidades e não autoriza execução.
    """

    def __init__(self, *, history_size: int = 1_000) -> None:
        if isinstance(history_size, bool):
            raise TypeError("history_size não pode ser booleano.")

        history_size = int(history_size)
        if history_size <= 0:
            raise ValueError("history_size deve ser maior que zero.")

        self._records: deque[dict[str, Any]] = deque(maxlen=history_size)
        self._lock = RLock()

    @staticmethod
    def _read(target: Any, field: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field, default)
        if target is None:
            return default
        return getattr(target, field, default)

    @classmethod
    def _analysis_from_opportunity(cls, opportunity: Any) -> Mapping[str, Any]:
        if isinstance(opportunity, Mapping):
            analysis = opportunity.get("ai_analysis")
            if isinstance(analysis, Mapping):
                return analysis

        metadata = getattr(opportunity, "metadata", None)
        if isinstance(metadata, Mapping):
            analysis = metadata.get("ai_analysis")
            if isinstance(analysis, Mapping):
                return analysis

        raise ValueError("A oportunidade não possui ai_analysis.")

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        if not isfinite(number):
            return None
        return number

    @staticmethod
    def _identifier(opportunity: Any) -> str | None:
        for field in ("opportunity_id", "id", "question"):
            if isinstance(opportunity, Mapping):
                value = opportunity.get(field)
            else:
                value = getattr(opportunity, field, None)
            if value is not None and str(value).strip():
                return str(value).strip()
        return None

    def record(
        self,
        analysis: Mapping[str, Any],
        *,
        opportunity_id: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(analysis, Mapping):
            raise TypeError("analysis deve ser um mapping.")

        status = str(
            analysis.get("prediction_status", "UNKNOWN") or "UNKNOWN"
        ).strip().upper()
        recommendation = str(
            analysis.get("recommendation", "REVIEW") or "REVIEW"
        ).strip().upper()
        warnings = [str(item) for item in analysis.get("warnings", [])]

        record = {
            "opportunity_id": (
                str(opportunity_id).strip() if opportunity_id else None
            ),
            "prediction_status": status,
            "analysis_status": str(
                analysis.get("analysis_status", "UNKNOWN") or "UNKNOWN"
            ).strip().upper(),
            "recommendation": recommendation,
            "heuristic_score": self._number(analysis.get("heuristic_score")),
            "model_probability": self._number(
                analysis.get("model_probability")
            ),
            "final_score": self._number(analysis.get("final_score")),
            "confidence": self._number(analysis.get("confidence")),
            "feature_coverage": self._number(
                analysis.get("feature_coverage")
            ),
            "model_version": (
                str(analysis.get("model_version")).strip()
                if analysis.get("model_version")
                else None
            ),
            "probability_calibrated": bool(
                analysis.get("probability_calibrated", False)
            ),
            "warnings": warnings,
            "advisory_only": True,
            "execution_authorized": False,
            "recorded_at": datetime.now(timezone.utc).isoformat(),
        }

        with self._lock:
            self._records.append(record)

        return deepcopy(record)

    def record_opportunity(self, opportunity: Any) -> dict[str, Any]:
        return self.record(
            self._analysis_from_opportunity(opportunity),
            opportunity_id=self._identifier(opportunity),
        )

    def record_many(self, opportunities: Iterable[Any]) -> int:
        if isinstance(opportunities, (str, bytes, Mapping)):
            raise TypeError("opportunities deve ser uma coleção.")

        count = 0
        for opportunity in opportunities:
            self.record_opportunity(opportunity)
            count += 1
        return count

    def all(self) -> list[dict[str, Any]]:
        with self._lock:
            return deepcopy(list(self._records))

    @property
    def last_record(self) -> dict[str, Any] | None:
        with self._lock:
            if not self._records:
                return None
            return deepcopy(self._records[-1])

    def clear(self) -> None:
        with self._lock:
            self._records.clear()

    reset = clear

    def summary(self) -> dict[str, Any]:
        records = self.all()
        statuses = Counter(record["prediction_status"] for record in records)
        recommendations = Counter(record["recommendation"] for record in records)

        def values(field: str) -> list[float]:
            return [
                float(record[field])
                for record in records
                if record.get(field) is not None
            ]

        final_scores = values("final_score")
        confidences = values("confidence")
        coverages = values("feature_coverage")
        model_versions = sorted(
            {
                record["model_version"]
                for record in records
                if record.get("model_version")
            }
        )

        return {
            "records": len(records),
            "prediction_statuses": dict(sorted(statuses.items())),
            "recommendations": dict(sorted(recommendations.items())),
            "model_predictions": sum(
                1 for record in records if record["model_probability"] is not None
            ),
            "heuristic_only": statuses.get("HEURISTIC_ONLY", 0),
            "invalid_features": statuses.get("INVALID_FEATURES", 0),
            "warnings": sum(len(record["warnings"]) for record in records),
            "average_final_score": round(mean(final_scores), 10)
            if final_scores
            else 0.0,
            "average_confidence": round(mean(confidences), 10)
            if confidences
            else 0.0,
            "average_feature_coverage": round(mean(coverages), 10)
            if coverages
            else 0.0,
            "model_versions": model_versions,
            "advisory_only": True,
            "execution_authorized": False,
        }

    snapshot = summary


prediction_monitor = PredictionMonitor()
