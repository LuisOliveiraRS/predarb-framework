from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.ai.models.model_metadata import ModelMetadata, ModelStatus


@dataclass(slots=True)
class ModelRecord:
    """Registro em memória de um modelo e seu estado operacional consultivo."""

    metadata: ModelMetadata
    model: Any = None
    status: ModelStatus = ModelStatus.REGISTERED
    source: str = "memory"
    activated_at: datetime | None = None
    deactivated_at: datetime | None = None
    loaded_from_artifact: bool = False
    registry_metadata: dict[str, Any] = field(default_factory=dict)

    advisory_only: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.metadata, ModelMetadata):
            raise TypeError("metadata deve ser ModelMetadata.")
        if not isinstance(self.status, ModelStatus):
            self.status = ModelStatus(str(self.status).strip().upper())
        self.source = str(self.source or "memory").strip() or "memory"
        self.registry_metadata = dict(self.registry_metadata or {})
        self.advisory_only = True
        self.execution_authorized = False

    @property
    def name(self) -> str:
        return self.metadata.name

    @property
    def version(self) -> str:
        return self.metadata.version

    @property
    def key(self) -> str:
        return self.metadata.key

    @property
    def model_loaded(self) -> bool:
        return self.model is not None

    @property
    def active(self) -> bool:
        return self.status is ModelStatus.ACTIVE

    @property
    def ready(self) -> bool:
        return self.active and self.model_loaded

    def attach_model(
        self,
        model: Any,
        *,
        source: str = "memory",
        loaded_from_artifact: bool = False,
    ) -> None:
        if model is None:
            raise ValueError("model não pode ser None.")
        self.model = model
        self.source = str(source or "memory").strip() or "memory"
        self.loaded_from_artifact = bool(loaded_from_artifact)

    def activate(self) -> None:
        if self.model is None:
            raise RuntimeError("MODEL_NOT_LOADED")
        self.status = ModelStatus.ACTIVE
        self.activated_at = datetime.now(timezone.utc)
        self.deactivated_at = None

    def deactivate(self) -> None:
        if self.status is ModelStatus.ARCHIVED:
            return
        self.status = ModelStatus.INACTIVE
        self.deactivated_at = datetime.now(timezone.utc)

    def archive(self) -> None:
        self.status = ModelStatus.ARCHIVED
        self.deactivated_at = datetime.now(timezone.utc)

    def clear_model(self) -> None:
        self.model = None
        if self.status is ModelStatus.ACTIVE:
            self.deactivate()

    def to_dict(self) -> dict[str, Any]:
        return {
            "metadata": self.metadata.to_dict(),
            "name": self.name,
            "version": self.version,
            "key": self.key,
            "status": self.status.value,
            "source": self.source,
            "model_loaded": self.model_loaded,
            "active": self.active,
            "ready": self.ready,
            "loaded_from_artifact": self.loaded_from_artifact,
            "activated_at": (
                self.activated_at.isoformat() if self.activated_at else None
            ),
            "deactivated_at": (
                self.deactivated_at.isoformat() if self.deactivated_at else None
            ),
            "registry_metadata": dict(self.registry_metadata),
            "advisory_only": True,
            "execution_authorized": False,
        }
