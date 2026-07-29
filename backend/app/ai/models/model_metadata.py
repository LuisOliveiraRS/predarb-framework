from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from enum import Enum
from re import fullmatch
from typing import Any, Mapping


_SAFE_IDENTIFIER = r"[A-Za-z0-9][A-Za-z0-9._-]{0,127}"


class ModelStatus(str, Enum):
    """Estados explícitos do ciclo de vida de um modelo."""

    REGISTERED = "REGISTERED"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


def _identifier(value: Any, field_name: str) -> str:
    text = str(value or "").strip()
    if not fullmatch(_SAFE_IDENTIFIER, text):
        raise ValueError(
            f"{field_name} deve usar apenas letras, números, ponto, "
            "hífen e underscore."
        )
    return text


def _datetime(value: Any, field_name: str) -> datetime:
    if isinstance(value, datetime):
        result = value
    elif isinstance(value, str):
        try:
            result = datetime.fromisoformat(value)
        except ValueError as exc:
            raise ValueError(f"{field_name} possui data inválida.") from exc
    else:
        raise TypeError(f"{field_name} deve ser datetime ou ISO-8601.")

    if result.tzinfo is None:
        result = result.replace(tzinfo=timezone.utc)
    return result.astimezone(timezone.utc)


@dataclass(slots=True)
class ModelMetadata:
    """
    Manifesto serializável de um modelo.

    O manifesto nunca contém o objeto Python do modelo. A camada de
    persistência grava somente metadados JSON e, opcionalmente, bytes de um
    artefato fornecido explicitamente pelo chamador.
    """

    name: str
    version: str
    model_type: str
    feature_names: tuple[str, ...]
    target_name: str = "success"
    probability_calibrated: bool = False
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    trained_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    registered_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    artifact_filename: str | None = None
    artifact_sha256: str | None = None
    artifact_size: int | None = None
    serializer: str | None = None
    trusted_artifact: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)

    advisory_only: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        self.name = _identifier(self.name, "name")
        self.version = _identifier(self.version, "version")
        self.model_type = str(self.model_type or "unknown").strip() or "unknown"
        self.target_name = str(self.target_name or "success").strip() or "success"

        feature_names = tuple(str(item).strip() for item in self.feature_names)
        if not feature_names or any(not item for item in feature_names):
            raise ValueError("feature_names deve conter ao menos uma feature válida.")
        if len(set(feature_names)) != len(feature_names):
            raise ValueError("feature_names não pode conter duplicidades.")
        self.feature_names = feature_names

        self.probability_calibrated = bool(self.probability_calibrated)
        self.metrics = dict(self.metrics or {})
        self.warnings = list(dict.fromkeys(str(item) for item in self.warnings))
        self.trained_at = _datetime(self.trained_at, "trained_at")
        self.registered_at = _datetime(self.registered_at, "registered_at")
        self.metadata = dict(self.metadata or {})

        if self.artifact_filename is not None:
            self.artifact_filename = _identifier(
                self.artifact_filename,
                "artifact_filename",
            )

        if self.artifact_sha256 is not None:
            digest = str(self.artifact_sha256).strip().lower()
            if not fullmatch(r"[0-9a-f]{64}", digest):
                raise ValueError("artifact_sha256 deve ser um SHA-256 hexadecimal.")
            self.artifact_sha256 = digest

        if self.artifact_size is not None:
            if isinstance(self.artifact_size, bool):
                raise TypeError("artifact_size não pode ser booleano.")
            self.artifact_size = int(self.artifact_size)
            if self.artifact_size < 0:
                raise ValueError("artifact_size não pode ser negativo.")

        self.serializer = (
            str(self.serializer).strip() if self.serializer is not None else None
        )
        self.trusted_artifact = bool(self.trusted_artifact)
        self.advisory_only = True
        self.execution_authorized = False

    @property
    def key(self) -> str:
        return f"{self.name}:{self.version}"

    @property
    def has_artifact(self) -> bool:
        return bool(
            self.artifact_filename
            and self.artifact_sha256
            and self.artifact_size is not None
        )

    def with_artifact(
        self,
        *,
        filename: str,
        sha256: str,
        size: int,
        serializer: str,
        trusted: bool,
    ) -> ModelMetadata:
        return replace(
            self,
            artifact_filename=filename,
            artifact_sha256=sha256,
            artifact_size=size,
            serializer=serializer,
            trusted_artifact=trusted,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "version": self.version,
            "key": self.key,
            "model_type": self.model_type,
            "feature_names": list(self.feature_names),
            "target_name": self.target_name,
            "probability_calibrated": self.probability_calibrated,
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "trained_at": self.trained_at.isoformat(),
            "registered_at": self.registered_at.isoformat(),
            "artifact_filename": self.artifact_filename,
            "artifact_sha256": self.artifact_sha256,
            "artifact_size": self.artifact_size,
            "serializer": self.serializer,
            "trusted_artifact": self.trusted_artifact,
            "has_artifact": self.has_artifact,
            "metadata": dict(self.metadata),
            "advisory_only": True,
            "execution_authorized": False,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> ModelMetadata:
        if not isinstance(data, Mapping):
            raise TypeError("data deve ser um mapping.")

        return cls(
            name=data.get("name", ""),
            version=data.get("version", ""),
            model_type=data.get("model_type", "unknown"),
            feature_names=tuple(data.get("feature_names", ())),
            target_name=data.get("target_name", "success"),
            probability_calibrated=bool(
                data.get("probability_calibrated", False)
            ),
            metrics=dict(data.get("metrics", {})),
            warnings=list(data.get("warnings", [])),
            trained_at=data.get("trained_at", datetime.now(timezone.utc)),
            registered_at=data.get(
                "registered_at",
                datetime.now(timezone.utc),
            ),
            artifact_filename=data.get("artifact_filename"),
            artifact_sha256=data.get("artifact_sha256"),
            artifact_size=data.get("artifact_size"),
            serializer=data.get("serializer"),
            trusted_artifact=bool(data.get("trusted_artifact", False)),
            metadata=dict(data.get("metadata", {})),
        )

    @classmethod
    def from_training_result(
        cls,
        result: Any,
        *,
        name: str = "opportunity",
        model_type: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> ModelMetadata:
        if result is None:
            raise ValueError("result não pode ser None.")

        version = getattr(result, "version", None)
        feature_names = tuple(getattr(result, "feature_names", ()))
        target_name = getattr(result, "target_name", "success")
        trained_at = getattr(result, "trained_at", datetime.now(timezone.utc))
        metrics = dict(getattr(result, "metrics", {}) or {})
        warnings = list(getattr(result, "warnings", []) or [])
        probability_calibrated = bool(
            getattr(result, "probability_calibrated", False)
        )
        model = getattr(result, "model", None)

        resolved_type = model_type or (
            type(model).__name__ if model is not None else "unknown"
        )

        return cls(
            name=name,
            version=version,
            model_type=resolved_type,
            feature_names=feature_names,
            target_name=target_name,
            probability_calibrated=probability_calibrated,
            metrics=metrics,
            warnings=warnings,
            trained_at=trained_at,
            metadata={
                "training_status": getattr(result, "status", None),
                "rows": getattr(result, "rows", None),
                "train_rows": getattr(result, "train_rows", None),
                "validation_rows": getattr(result, "validation_rows", None),
                **dict(metadata or {}),
            },
        )
