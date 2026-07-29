from __future__ import annotations

from copy import deepcopy
from typing import Any

from app.ai.predictors.opportunity_predictor import (
    OpportunityPredictor,
    opportunity_predictor,
)
from app.ai.registry.model_registry import ModelRegistry, model_registry


class InferenceService:
    """Ativa modelos em memória no predictor consultivo."""

    def __init__(
        self,
        *,
        predictor: OpportunityPredictor | None = None,
        registry: ModelRegistry | None = None,
    ) -> None:
        self.predictor = predictor or opportunity_predictor
        self.registry = registry or model_registry
        self.last_report: dict[str, Any] = {}

    def activate(self, name: str, version: str) -> Any:
        record = self.registry.activate(name, version, require_loaded=True)
        self.predictor.set_model(
            record.model,
            version=record.version,
            probability_calibrated=record.metadata.probability_calibrated,
        )
        self.last_report = {
            "operation": "ACTIVATE",
            "name": record.name,
            "version": record.version,
            "probability_calibrated": record.metadata.probability_calibrated,
        }
        return record

    def deactivate(self, name: str = "opportunity") -> Any:
        record = self.registry.deactivate(name)
        self.predictor.clear_model()
        self.last_report = {
            "operation": "DEACTIVATE",
            "name": str(name),
            "version": record.version if record else None,
        }
        return record

    def predict(self, features: dict[str, float]) -> Any:
        return self.predictor.predict(features)

    def status(self) -> dict[str, Any]:
        active = self.registry.active("opportunity")
        return {
            "predictor": self.predictor.status(),
            "active_model": active.to_dict() if active else None,
            "last_report": deepcopy(self.last_report),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


inference_service = InferenceService()

inference_service_instance = inference_service
