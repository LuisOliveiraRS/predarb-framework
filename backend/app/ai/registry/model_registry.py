from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from app.ai.models.model_metadata import ModelMetadata, ModelStatus
from app.ai.models.model_record import ModelRecord


class ModelRegistry:
    """Registro thread-safe de modelos em memória."""

    def __init__(self) -> None:
        self._records: dict[str, dict[str, ModelRecord]] = {}
        self._active: dict[str, str] = {}
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    def register(
        self,
        value: ModelRecord | ModelMetadata,
        *,
        model: Any = None,
        replace: bool = False,
        source: str = "memory",
    ) -> ModelRecord:
        if isinstance(value, ModelRecord):
            record = value
            if model is not None:
                record.attach_model(model, source=source)
        elif isinstance(value, ModelMetadata):
            record = ModelRecord(
                metadata=value,
                model=model,
                source=source,
            )
        else:
            raise TypeError("value deve ser ModelRecord ou ModelMetadata.")

        with self._lock:
            versions = self._records.setdefault(record.name, {})
            if record.version in versions and not replace:
                raise ValueError(f"MODEL_VERSION_ALREADY_REGISTERED:{record.key}")

            if replace and self._active.get(record.name) == record.version:
                record.status = ModelStatus.ACTIVE
                record.activated_at = versions[record.version].activated_at

            versions[record.version] = record

        self.last_report = {
            "operation": "REGISTER",
            "name": record.name,
            "version": record.version,
            "model_loaded": record.model_loaded,
            "replace": bool(replace),
        }
        return record

    def get(self, name: str, version: str) -> ModelRecord | None:
        with self._lock:
            return self._records.get(str(name), {}).get(str(version))

    def require(self, name: str, version: str) -> ModelRecord:
        record = self.get(name, version)
        if record is None:
            raise KeyError(f"MODEL_NOT_REGISTERED:{name}:{version}")
        return record

    def active(self, name: str = "opportunity") -> ModelRecord | None:
        with self._lock:
            version = self._active.get(str(name))
            if version is None:
                return None
            return self._records.get(str(name), {}).get(version)

    def activate(
        self,
        name: str,
        version: str,
        *,
        require_loaded: bool = True,
    ) -> ModelRecord:
        with self._lock:
            record = self.require(name, version)
            if require_loaded and not record.model_loaded:
                raise RuntimeError("MODEL_NOT_LOADED")

            current_version = self._active.get(record.name)
            if current_version and current_version != record.version:
                current = self._records[record.name][current_version]
                current.deactivate()

            record.activate()
            self._active[record.name] = record.version

        self.last_report = {
            "operation": "ACTIVATE",
            "name": record.name,
            "version": record.version,
        }
        return record

    def deactivate(self, name: str = "opportunity") -> ModelRecord | None:
        with self._lock:
            version = self._active.pop(str(name), None)
            if version is None:
                return None
            record = self._records[str(name)][version]
            record.deactivate()

        self.last_report = {
            "operation": "DEACTIVATE",
            "name": record.name,
            "version": record.version,
        }
        return record

    def versions(self, name: str) -> list[str]:
        with self._lock:
            return sorted(self._records.get(str(name), {}))

    def all(self, name: str | None = None) -> list[ModelRecord]:
        with self._lock:
            if name is not None:
                return list(self._records.get(str(name), {}).values())
            return [
                record
                for versions in self._records.values()
                for record in versions.values()
            ]

    def remove(self, name: str, version: str) -> ModelRecord | None:
        with self._lock:
            versions = self._records.get(str(name))
            if not versions:
                return None
            record = versions.pop(str(version), None)
            if record is None:
                return None
            if self._active.get(str(name)) == str(version):
                self._active.pop(str(name), None)
                record.deactivate()
            if not versions:
                self._records.pop(str(name), None)

        self.last_report = {
            "operation": "REMOVE",
            "name": str(name),
            "version": str(version),
        }
        return record

    def clear(self) -> None:
        with self._lock:
            for record in self.all():
                if record.active:
                    record.deactivate()
            self._records.clear()
            self._active.clear()
        self.last_report = {"operation": "CLEAR"}

    def status(self) -> dict[str, Any]:
        records = self.all()
        return {
            "models": len({record.name for record in records}),
            "versions": len(records),
            "loaded": sum(record.model_loaded for record in records),
            "active": dict(sorted(self._active.items())),
            "records": [record.to_dict() for record in records],
            "last_report": deepcopy(self.last_report),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


model_registry = ModelRegistry()

model_registry_service = model_registry
