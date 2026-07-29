from __future__ import annotations

from typing import Any

from app.ai.ai_engine import AIEngine, ai_engine
from app.ai.monitoring.prediction_monitor import (
    PredictionMonitor,
    prediction_monitor,
)


class AIMonitor:
    """Agrega o estado do predictor e o histórico de inferências."""

    def __init__(
        self,
        *,
        engine: AIEngine | None = None,
        predictions: PredictionMonitor | None = None,
    ) -> None:
        self.engine = engine or ai_engine
        self.predictions = predictions or prediction_monitor

    def snapshot(self) -> dict[str, Any]:
        predictor_status = self.engine.predictor.status()
        return {
            "status": "ONLINE",
            "predictor": predictor_status,
            "predictions": self.predictions.summary(),
            "last_engine_report": dict(self.engine.last_report),
            "advisory_only": True,
            "execution_authorized": False,
        }

    status = snapshot


ai_monitor = AIMonitor()
