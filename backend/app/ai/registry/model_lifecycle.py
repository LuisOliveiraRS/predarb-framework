from __future__ import annotations

from copy import deepcopy
from typing import Any, Callable, Mapping

from app.ai.inference.inference_service import (
    InferenceService,
    inference_service,
)
from app.ai.inference.model_loader import ModelLoader, model_loader
from app.ai.model_repository import ModelRepository, model_repository
from app.ai.models.model_metadata import ModelMetadata
from app.ai.models.model_record import ModelRecord
from app.ai.registry.model_registry import ModelRegistry, model_registry


class ModelLifecycleService:
    """Orquestra registro, persistência, carregamento e ativação explícita."""

    def __init__(
        self,
        *,
        registry: ModelRegistry | None = None,
        repository: ModelRepository | None = None,
        loader: ModelLoader | None = None,
        inference: InferenceService | None = None,
    ) -> None:
        self.registry = registry or ModelRegistry()
        self.repository = repository or model_repository
        self.loader = loader or ModelLoader(self.repository)
        self.inference = inference or InferenceService(registry=self.registry)
        self.last_report: dict[str, Any] = {}

    def register_training(
        self,
        result: Any,
        *,
        name: str = "opportunity",
        model_type: str | None = None,
        replace: bool = False,
        persist_metadata: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> ModelRecord:
        model = getattr(result, "model", None)
        if model is None:
            raise ValueError("TrainingResult não possui model.")

        manifest = ModelMetadata.from_training_result(
            result,
            name=name,
            model_type=model_type,
            metadata=metadata,
        )
        record = self.registry.register(
            manifest,
            model=model,
            replace=replace,
            source="training",
        )

        if persist_metadata:
            self.repository.save_metadata(record)

        self.last_report = {
            "operation": "REGISTER_TRAINING",
            "name": record.name,
            "version": record.version,
            "persisted_metadata": bool(persist_metadata),
            "artifact_persisted": False,
        }
        return record

    def register_model(
        self,
        model: Any,
        metadata: ModelMetadata,
        *,
        replace: bool = False,
        persist_metadata: bool = False,
        source: str = "manual",
    ) -> ModelRecord:
        record = self.registry.register(
            metadata,
            model=model,
            replace=replace,
            source=source,
        )
        if persist_metadata:
            self.repository.save_metadata(record)
        self.last_report = {
            "operation": "REGISTER_MODEL",
            "name": record.name,
            "version": record.version,
            "persisted_metadata": bool(persist_metadata),
        }
        return record

    def persist(
        self,
        name: str,
        version: str,
        *,
        artifact: bytes | bytearray | memoryview | None = None,
        artifact_filename: str = "model.bin",
        serializer: str = "external",
        trusted_artifact: bool = False,
    ) -> ModelMetadata:
        record = self.registry.require(name, version)
        metadata = self.repository.save(
            record,
            artifact=artifact,
            artifact_filename=artifact_filename,
            serializer=serializer,
            trusted_artifact=trusted_artifact,
        )
        self.last_report = {
            "operation": "PERSIST",
            "name": name,
            "version": version,
            "artifact_persisted": artifact is not None,
            "trusted_artifact": metadata.trusted_artifact,
        }
        return metadata

    def load(
        self,
        name: str,
        version: str,
        *,
        loader: Callable[..., Any],
        trusted: bool = False,
        expected_serializer: str | None = None,
        activate: bool = False,
        replace: bool = False,
    ) -> ModelRecord:
        model, metadata = self.loader.load(
            name,
            version,
            loader=loader,
            trusted=trusted,
            expected_serializer=expected_serializer,
        )
        record = self.registry.register(
            metadata,
            model=model,
            replace=replace,
            source="artifact",
        )
        record.loaded_from_artifact = True

        if activate:
            self.inference.activate(name, version)

        self.last_report = {
            "operation": "LOAD",
            "name": name,
            "version": version,
            "activated": bool(activate),
            "checksum_verified": True,
        }
        return record

    def activate(self, name: str, version: str) -> ModelRecord:
        record = self.inference.activate(name, version)
        self.last_report = {
            "operation": "ACTIVATE",
            "name": name,
            "version": version,
        }
        return record

    def deactivate(self, name: str = "opportunity") -> ModelRecord | None:
        record = self.inference.deactivate(name)
        self.last_report = {
            "operation": "DEACTIVATE",
            "name": name,
            "version": record.version if record else None,
        }
        return record

    def remove(
        self,
        name: str,
        version: str,
        *,
        remove_artifact: bool = False,
    ) -> ModelRecord | None:
        active = self.registry.active(name)
        if active and active.version == version:
            self.deactivate(name)

        record = self.registry.remove(name, version)
        artifact_removed = (
            self.repository.remove(name, version) if remove_artifact else False
        )
        self.last_report = {
            "operation": "REMOVE",
            "name": name,
            "version": version,
            "registry_removed": record is not None,
            "artifact_removed": artifact_removed,
        }
        return record

    def status(self) -> dict[str, Any]:
        return {
            "registry": self.registry.status(),
            "repository": self.repository.status(),
            "loader": self.loader.status(),
            "inference": self.inference.status(),
            "last_report": deepcopy(self.last_report),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


model_lifecycle = ModelLifecycleService(
    registry=model_registry,
    repository=model_repository,
    loader=model_loader,
    inference=inference_service,
)

model_lifecycle_service = model_lifecycle
