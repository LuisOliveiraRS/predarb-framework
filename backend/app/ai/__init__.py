"""API pública lazy e segura da camada AI."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "AIEngine": ("app.ai.ai_engine", "AIEngine"),
    "ai_engine": ("app.ai.ai_engine", "ai_engine"),
    "AIRuntime": ("app.ai.runtime", "AIRuntime"),
    "ai_runtime": ("app.ai.runtime", "ai_runtime"),
    "BasePredictor": ("app.ai.predictors", "BasePredictor"),
    "OpportunityPredictor": ("app.ai.predictors", "OpportunityPredictor"),
    "PredictionResult": ("app.ai.predictors", "PredictionResult"),
    "PredictionStatus": ("app.ai.predictors", "PredictionStatus"),
    "BaseTrainer": ("app.ai.trainers", "BaseTrainer"),
    "Trainer": ("app.ai.trainers", "Trainer"),
    "TrainingResult": ("app.ai.trainers", "TrainingResult"),
    "DatasetBuilder": ("app.ai.datasets", "DatasetBuilder"),
    "DatasetReader": ("app.ai.datasets", "DatasetReader"),
    "DatasetRepository": ("app.ai.datasets", "DatasetRepository"),
    "DatasetStatistics": ("app.ai.datasets", "DatasetStatistics"),
    "DatasetValidator": ("app.ai.datasets", "DatasetValidator"),
    "DatasetWriter": ("app.ai.datasets", "DatasetWriter"),
    "Feature": ("app.ai.feature_store", "Feature"),
    "FeatureBuilder": ("app.ai.feature_store", "FeatureBuilder"),
    "FeatureStore": ("app.ai.feature_store", "FeatureStore"),
    "AIAnalysisPipeline": ("app.ai.pipelines", "AIAnalysisPipeline"),
    "ai_analysis_pipeline": ("app.ai.pipelines", "ai_analysis_pipeline"),
    "AIMonitor": ("app.ai.monitoring", "AIMonitor"),
    "PredictionMonitor": ("app.ai.monitoring", "PredictionMonitor"),
    "ai_monitor": ("app.ai.monitoring", "ai_monitor"),
    "prediction_monitor": ("app.ai.monitoring", "prediction_monitor"),
    "ModelMetadata": ("app.ai.models", "ModelMetadata"),
    "ModelRecord": ("app.ai.models", "ModelRecord"),
    "ModelStatus": ("app.ai.models", "ModelStatus"),
    "ModelRepository": ("app.ai.model_repository", "ModelRepository"),
    "model_repository_service": (
        "app.ai.model_repository",
        "model_repository_service",
    ),
    "ModelRegistry": ("app.ai.registry", "ModelRegistry"),
    "ModelLifecycleService": ("app.ai.registry", "ModelLifecycleService"),
    "model_registry_service": (
        "app.ai.registry",
        "model_registry_service",
    ),
    "model_lifecycle_service": (
        "app.ai.registry",
        "model_lifecycle_service",
    ),
    "ModelLoader": ("app.ai.inference", "ModelLoader"),
    "InferenceService": ("app.ai.inference", "InferenceService"),
    "model_loader_service": (
        "app.ai.inference",
        "model_loader_service",
    ),
    "inference_service_instance": (
        "app.ai.inference",
        "inference_service_instance",
    ),
}


__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(f"module 'app.ai' has no attribute {name!r}") from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
