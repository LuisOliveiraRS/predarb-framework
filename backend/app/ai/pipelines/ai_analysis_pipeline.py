from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.ai.ai_engine import AIEngine, ai_engine
from app.ai.monitoring.prediction_monitor import (
    PredictionMonitor,
    prediction_monitor,
)


class AIAnalysisPipeline:
    """
    Pipeline consultivo da camada AI.

    Ele apenas anexa ``ai_analysis`` às oportunidades e registra métricas de
    inferência. Nenhuma decisão operacional é alterada.
    """

    def __init__(
        self,
        *,
        engine: AIEngine | None = None,
        monitor: PredictionMonitor | None = None,
    ) -> None:
        self.engine = engine or ai_engine
        self.monitor = monitor or prediction_monitor
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(opportunities: Any) -> list[Any]:
        if opportunities is None:
            return []
        if isinstance(opportunities, Mapping):
            return [opportunities]
        if isinstance(opportunities, (str, bytes)):
            raise TypeError("opportunities deve ser uma coleção.")
        if isinstance(opportunities, Iterable):
            return list(opportunities)
        return [opportunities]

    def analyze(
        self,
        opportunities: Any,
        *,
        strict_features: bool = False,
        copy_results: bool = True,
    ) -> list[Any]:
        items = self._as_list(opportunities)
        analyzed = self.engine.analyze(
            items,
            strict_features=strict_features,
            copy_results=copy_results,
        )

        recorded = 0
        monitoring_errors: list[str] = []
        for opportunity in analyzed:
            try:
                self.monitor.record_opportunity(opportunity)
                recorded += 1
            except (TypeError, ValueError) as exc:
                monitoring_errors.append(str(exc))

        self.last_report = {
            **dict(self.engine.last_report),
            "input": len(items),
            "analyzed": len(analyzed),
            "monitoring_records": recorded,
            "monitoring_errors": monitoring_errors,
            "monitoring": self.monitor.summary(),
            "advisory_only": True,
            "execution_authorized": False,
        }
        return analyzed

    def analyze_one(
        self,
        opportunity: Any,
        *,
        strict_features: bool = False,
        copy_result: bool = True,
    ) -> Any:
        results = self.analyze(
            [opportunity],
            strict_features=strict_features,
            copy_results=copy_result,
        )
        return results[0]

    def status(self) -> dict[str, Any]:
        return {
            "engine": {
                "predictor": self.engine.predictor.status(),
                "last_report": dict(self.engine.last_report),
            },
            "monitoring": self.monitor.summary(),
            "last_report": dict(self.last_report),
            "advisory_only": True,
            "execution_authorized": False,
        }


ai_analysis_pipeline = AIAnalysisPipeline()
