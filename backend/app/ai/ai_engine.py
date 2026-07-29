from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import TYPE_CHECKING, Any, Callable

import pandas as pd

from app.core.settings import settings

from app.ai.feature_store.feature_builder import FeatureBuilder, feature_builder
from app.ai.inference.inference_service import InferenceService
from app.ai.inference.model_loader import ModelLoader
from app.ai.model_repository import ModelRepository, model_repository
from app.ai.models.model_metadata import ModelMetadata
from app.ai.predictors.opportunity_predictor import (
    OpportunityPredictor,
    opportunity_predictor,
)
from app.ai.registry.model_lifecycle import ModelLifecycleService
from app.ai.registry.model_registry import ModelRegistry

if TYPE_CHECKING:
    from app.ai.trainers.base_trainer import TrainingResult
    from app.ai.trainers.trainer import Trainer


class AIEngine:
    """
    Fachada consultiva da camada AI.

    O Trainer é carregado somente quando treinamento é solicitado. Modelos
    permanecem em memória até que persistência e carregamento sejam chamados
    explicitamente. Nenhum modelo é carregado automaticamente na inicialização.
    """

    DEFAULT_MODEL_NAME = settings.AI_MODEL_NAME

    def __init__(
        self,
        *,
        builder: FeatureBuilder | None = None,
        predictor: OpportunityPredictor | None = None,
        trainer_service: Trainer | None = None,
        lifecycle: ModelLifecycleService | None = None,
        repository: ModelRepository | None = None,
    ) -> None:
        self.builder = builder or feature_builder
        self.predictor = predictor or opportunity_predictor
        self._trainer = trainer_service

        if lifecycle is None:
            registry = ModelRegistry()
            resolved_repository = repository or model_repository
            inference = InferenceService(
                predictor=self.predictor,
                registry=registry,
            )
            lifecycle = ModelLifecycleService(
                registry=registry,
                repository=resolved_repository,
                loader=ModelLoader(resolved_repository),
                inference=inference,
            )

        self.lifecycle = lifecycle
        self.last_report: dict[str, Any] = {}

    @property
    def trainer(self) -> Trainer:
        if self._trainer is None:
            from app.ai.trainers.trainer import trainer

            self._trainer = trainer
        return self._trainer

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

    @staticmethod
    def _attach(target: Any, analysis: dict[str, Any]) -> None:
        if isinstance(target, dict):
            target["ai_analysis"] = analysis
            target["ai_prediction"] = analysis["final_score"]
            target["ai_prediction_scale"] = "0_to_1"
            return

        metadata = getattr(target, "metadata", None)
        if isinstance(metadata, dict):
            metadata["ai_analysis"] = analysis
            metadata["ai_prediction"] = analysis["final_score"]
            metadata["ai_prediction_scale"] = "0_to_1"

        if hasattr(target, "ai_prediction"):
            try:
                setattr(target, "ai_prediction", analysis["final_score"])
            except (AttributeError, TypeError):
                pass

    def analyze_one(
        self,
        opportunity: Any,
        *,
        strict_features: bool = False,
        copy_result: bool = True,
    ) -> Any:
        if opportunity is None:
            raise ValueError("opportunity não pode ser None.")

        target = deepcopy(opportunity) if copy_result else opportunity

        try:
            features = self.builder.build(
                opportunity,
                strict=strict_features,
            )
            feature_report = dict(self.builder.last_report)
            prediction = self.predictor.predict(features)
            analysis = prediction.to_dict()
            analysis["features"] = dict(features)
            analysis["feature_report"] = feature_report
            analysis["analysis_status"] = (
                "READY" if feature_report.get("valid") else "DEGRADED"
            )
        except (TypeError, ValueError) as exc:
            if strict_features:
                raise

            analysis = {
                "heuristic_score": 0.0,
                "model_probability": None,
                "final_score": 0.0,
                "confidence": 0.0,
                "model_version": None,
                "probability_calibrated": False,
                "prediction_status": "INVALID_FEATURES",
                "feature_coverage": 0.0,
                "recommendation": "REVIEW",
                "warnings": [str(exc)],
                "metadata": {},
                "features": {},
                "feature_report": dict(self.builder.last_report),
                "analysis_status": "INVALID",
                "advisory_only": True,
                "execution_authorized": False,
            }

        analysis["advisory_only"] = True
        analysis["execution_authorized"] = False
        self._attach(target, analysis)
        return target

    def analyze(
        self,
        opportunities: Any,
        *,
        strict_features: bool = False,
        copy_results: bool = True,
    ) -> list[Any]:
        items = self._as_list(opportunities)
        analyzed: list[Any] = []
        statuses: dict[str, int] = {}

        for opportunity in items:
            result = self.analyze_one(
                opportunity,
                strict_features=strict_features,
                copy_result=copy_results,
            )
            analyzed.append(result)

            if isinstance(result, Mapping):
                status = result["ai_analysis"]["prediction_status"]
            else:
                status = getattr(result, "metadata", {}).get(
                    "ai_analysis",
                    {},
                ).get("prediction_status", "UNKNOWN")
            statuses[status] = statuses.get(status, 0) + 1

        active = self.lifecycle.registry.active(self.DEFAULT_MODEL_NAME)
        self.last_report = {
            "input": len(items),
            "analyzed": len(analyzed),
            "prediction_statuses": dict(sorted(statuses.items())),
            "model_loaded": self.predictor.model is not None,
            "model_version": self.predictor.model_version,
            "active_model": active.version if active else None,
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }
        return analyzed

    def train(
        self,
        dataframe: pd.DataFrame,
        *,
        activate: bool = True,
        calibrate: bool = False,
        test_size: float = 0.25,
        calibration_cv: int = 3,
        model_name: str = DEFAULT_MODEL_NAME,
        persist_metadata: bool = False,
        replace: bool = True,
    ) -> TrainingResult:
        result = self.trainer.fit(
            dataframe,
            calibrate=calibrate,
            test_size=test_size,
            calibration_cv=calibration_cv,
        )

        record = self.lifecycle.register_training(
            result,
            name=model_name,
            replace=replace,
            persist_metadata=persist_metadata,
        )

        if activate:
            self.lifecycle.activate(record.name, record.version)

        self.last_report = {
            "operation": "TRAIN",
            "registered": True,
            "activated": bool(activate),
            "persisted_metadata": bool(persist_metadata),
            "artifact_persisted": False,
            "model_name": record.name,
            "model_version": record.version,
            "training": result.to_dict(),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }
        return result

    def register_model(
        self,
        model: Any,
        *,
        version: str,
        probability_calibrated: bool = False,
        model_name: str = DEFAULT_MODEL_NAME,
        model_type: str | None = None,
        activate: bool = True,
        replace: bool = True,
        persist_metadata: bool = False,
    ) -> None:
        metadata = ModelMetadata(
            name=model_name,
            version=version,
            model_type=model_type or type(model).__name__,
            feature_names=tuple(self.predictor.feature_names),
            target_name="success",
            probability_calibrated=probability_calibrated,
            metadata={"registration": "manual"},
        )
        record = self.lifecycle.register_model(
            model,
            metadata,
            replace=replace,
            persist_metadata=persist_metadata,
            source="manual",
        )
        if activate:
            self.lifecycle.activate(record.name, record.version)

        self.last_report = {
            "operation": "REGISTER_MODEL",
            "model_name": record.name,
            "model_version": record.version,
            "activated": bool(activate),
            "persisted_metadata": bool(persist_metadata),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }

    def persist_model(
        self,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
        version: str | None = None,
        artifact: bytes | bytearray | memoryview | None = None,
        artifact_filename: str = "model.bin",
        serializer: str = "external",
        trusted_artifact: bool = False,
    ) -> ModelMetadata:
        record = (
            self.lifecycle.registry.active(model_name)
            if version is None
            else self.lifecycle.registry.get(model_name, version)
        )
        if record is None:
            raise KeyError("MODEL_NOT_REGISTERED")

        metadata = self.lifecycle.persist(
            record.name,
            record.version,
            artifact=artifact,
            artifact_filename=artifact_filename,
            serializer=serializer,
            trusted_artifact=trusted_artifact,
        )
        self.last_report = {
            "operation": "PERSIST_MODEL",
            "model_name": metadata.name,
            "model_version": metadata.version,
            "artifact_persisted": artifact is not None,
            "trusted_artifact": metadata.trusted_artifact,
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }
        return metadata

    def load_model(
        self,
        *,
        model_name: str,
        version: str,
        loader: Callable[..., Any],
        trusted: bool = False,
        expected_serializer: str | None = None,
        activate: bool = False,
        replace: bool = False,
    ) -> Any:
        record = self.lifecycle.load(
            model_name,
            version,
            loader=loader,
            trusted=trusted,
            expected_serializer=expected_serializer,
            activate=activate,
            replace=replace,
        )
        self.last_report = {
            "operation": "LOAD_MODEL",
            "model_name": record.name,
            "model_version": record.version,
            "activated": bool(activate),
            "checksum_verified": True,
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }
        return record

    def activate_model(
        self,
        version: str,
        *,
        model_name: str = DEFAULT_MODEL_NAME,
    ) -> Any:
        record = self.lifecycle.activate(model_name, version)
        self.last_report = {
            "operation": "ACTIVATE_MODEL",
            "model_name": record.name,
            "model_version": record.version,
            "advisory_only": True,
            "execution_authorized": False,
        }
        return record

    def clear_model(self) -> None:
        self.lifecycle.deactivate(self.DEFAULT_MODEL_NAME)
        # Compatibilidade para predictors registrados fora do lifecycle.
        self.predictor.clear_model()
        self.last_report = {
            "operation": "CLEAR_MODEL",
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }

    deactivate_model = clear_model

    def status(self, *, include_trainer: bool = True) -> dict[str, Any]:
        trainer_status: dict[str, Any]
        if include_trainer:
            trainer_status = self.trainer.status()
        elif self._trainer is not None:
            trainer_status = self._trainer.status()
        else:
            trainer_status = {
                "loaded": False,
                "status": "NOT_INITIALIZED",
            }

        return {
            "predictor": self.predictor.status(),
            "trainer": trainer_status,
            "models": self.lifecycle.status(),
            "last_report": dict(self.last_report),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


ai_engine = AIEngine()
