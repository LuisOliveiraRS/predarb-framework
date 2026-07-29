from __future__ import annotations

import json
import os
import shutil

from copy import deepcopy
from hashlib import sha256
from pathlib import Path
from tempfile import NamedTemporaryFile
from threading import RLock
from typing import Any

from app.core.settings import settings

from app.ai.models.model_metadata import ModelMetadata
from app.ai.models.model_record import ModelRecord


class ModelRepository:
    """
    Repositório seguro de manifestos e bytes de artefatos.

    O repositório não serializa objetos Python e nunca executa ou desserializa
    o conteúdo de um artefato. O carregamento exige um loader explícito na
    camada ``inference``.
    """

    METADATA_FILENAME = "metadata.json"
    DEFAULT_ARTIFACT_FILENAME = "model.bin"

    def __init__(self, root: str | Path = "model_artifacts") -> None:
        self.root = Path(root).expanduser()
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    def ensure(self) -> Path:
        self.root.mkdir(parents=True, exist_ok=True)
        return self.root

    @staticmethod
    def _safe_part(value: Any, field_name: str) -> str:
        from app.ai.models.model_metadata import _identifier

        return _identifier(value, field_name)

    def directory(self, name: str, version: str, *, create: bool = False) -> Path:
        safe_name = self._safe_part(name, "name")
        safe_version = self._safe_part(version, "version")
        path = self.root / safe_name / safe_version
        if create:
            path.mkdir(parents=True, exist_ok=True)
        return path

    def metadata_path(self, name: str, version: str) -> Path:
        return self.directory(name, version) / self.METADATA_FILENAME

    def artifact_path(
        self,
        name: str,
        version: str,
        *,
        metadata: ModelMetadata | None = None,
    ) -> Path:
        resolved = metadata or self.read_metadata(name, version)
        if not resolved.artifact_filename:
            raise FileNotFoundError("MODEL_ARTIFACT_NOT_REGISTERED")
        return self.directory(name, version) / resolved.artifact_filename

    @staticmethod
    def _atomic_write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with NamedTemporaryFile(
            mode="wb",
            dir=path.parent,
            prefix=f".{path.name}.",
            delete=False,
        ) as temporary:
            temporary.write(data)
            temporary.flush()
            os.fsync(temporary.fileno())
            temporary_path = Path(temporary.name)

        try:
            temporary_path.replace(path)
        finally:
            if temporary_path.exists():
                temporary_path.unlink(missing_ok=True)

    @staticmethod
    def _metadata_from(value: ModelMetadata | ModelRecord) -> ModelMetadata:
        if isinstance(value, ModelRecord):
            return value.metadata
        if isinstance(value, ModelMetadata):
            return value
        raise TypeError("value deve ser ModelMetadata ou ModelRecord.")

    def save_metadata(self, value: ModelMetadata | ModelRecord) -> Path:
        metadata = self._metadata_from(value)
        data = json.dumps(
            metadata.to_dict(),
            ensure_ascii=False,
            sort_keys=True,
            indent=2,
        ).encode("utf-8")
        path = self.metadata_path(metadata.name, metadata.version)

        with self._lock:
            self._atomic_write(path, data)

        self.last_report = {
            "operation": "SAVE_METADATA",
            "name": metadata.name,
            "version": metadata.version,
            "path": str(path),
            "artifact_saved": False,
        }
        return path

    def save(
        self,
        value: ModelMetadata | ModelRecord,
        *,
        artifact: bytes | bytearray | memoryview | None = None,
        artifact_filename: str = DEFAULT_ARTIFACT_FILENAME,
        serializer: str = "external",
        trusted_artifact: bool = False,
    ) -> ModelMetadata:
        metadata = self._metadata_from(value)
        artifact_saved = False

        if artifact is not None:
            if isinstance(artifact, memoryview):
                raw = artifact.tobytes()
            elif isinstance(artifact, (bytes, bytearray)):
                raw = bytes(artifact)
            else:
                raise TypeError("artifact deve ser bytes-like.")

            filename = self._safe_part(artifact_filename, "artifact_filename")
            digest = sha256(raw).hexdigest()
            metadata = metadata.with_artifact(
                filename=filename,
                sha256=digest,
                size=len(raw),
                serializer=str(serializer or "external").strip() or "external",
                trusted=bool(trusted_artifact),
            )

            with self._lock:
                artifact_path = self.directory(
                    metadata.name,
                    metadata.version,
                    create=True,
                ) / filename
                self._atomic_write(artifact_path, raw)
            artifact_saved = True

            if isinstance(value, ModelRecord):
                value.metadata = metadata

        path = self.save_metadata(metadata)
        self.last_report = {
            "operation": "SAVE",
            "name": metadata.name,
            "version": metadata.version,
            "path": str(path),
            "artifact_saved": artifact_saved,
            "trusted_artifact": metadata.trusted_artifact,
            "serializer": metadata.serializer,
        }
        return metadata

    def read_metadata(self, name: str, version: str) -> ModelMetadata:
        path = self.metadata_path(name, version)
        if not path.is_file():
            raise FileNotFoundError(f"Model metadata não encontrado: {name}:{version}")

        with self._lock:
            data = json.loads(path.read_text(encoding="utf-8"))

        metadata = ModelMetadata.from_dict(data)
        self.last_report = {
            "operation": "READ_METADATA",
            "name": metadata.name,
            "version": metadata.version,
            "path": str(path),
        }
        return metadata

    def read_artifact_bytes(
        self,
        name: str,
        version: str,
        *,
        verify: bool = True,
    ) -> bytes:
        metadata = self.read_metadata(name, version)
        path = self.artifact_path(name, version, metadata=metadata)
        if not path.is_file():
            raise FileNotFoundError(f"Model artifact não encontrado: {path}")

        with self._lock:
            raw = path.read_bytes()

        if verify:
            digest = sha256(raw).hexdigest()
            if digest != metadata.artifact_sha256:
                raise ValueError("MODEL_ARTIFACT_CHECKSUM_MISMATCH")
            if len(raw) != metadata.artifact_size:
                raise ValueError("MODEL_ARTIFACT_SIZE_MISMATCH")

        self.last_report = {
            "operation": "READ_ARTIFACT",
            "name": metadata.name,
            "version": metadata.version,
            "path": str(path),
            "verified": bool(verify),
            "size": len(raw),
        }
        return raw

    def exists(self, name: str, version: str) -> bool:
        return self.metadata_path(name, version).is_file()

    def versions(self, name: str) -> list[str]:
        safe_name = self._safe_part(name, "name")
        directory = self.root / safe_name
        if not directory.is_dir():
            return []
        return sorted(
            child.name
            for child in directory.iterdir()
            if child.is_dir() and (child / self.METADATA_FILENAME).is_file()
        )

    def list(self, name: str | None = None) -> list[dict[str, Any]]:
        manifests: list[dict[str, Any]] = []
        if name is not None:
            names = [self._safe_part(name, "name")]
        elif self.root.is_dir():
            names = sorted(child.name for child in self.root.iterdir() if child.is_dir())
        else:
            names = []

        for model_name in names:
            for version in self.versions(model_name):
                try:
                    manifests.append(
                        self.read_metadata(model_name, version).to_dict()
                    )
                except (OSError, ValueError, TypeError, json.JSONDecodeError):
                    continue
        return deepcopy(manifests)

    def remove(self, name: str, version: str) -> bool:
        directory = self.directory(name, version)
        if not directory.exists():
            return False

        with self._lock:
            shutil.rmtree(directory)
            parent = directory.parent
            if parent.is_dir() and not any(parent.iterdir()):
                parent.rmdir()

        self.last_report = {
            "operation": "REMOVE",
            "name": self._safe_part(name, "name"),
            "version": self._safe_part(version, "version"),
        }
        return True

    def status(self) -> dict[str, Any]:
        manifests = self.list()
        return {
            "root": str(self.root),
            "exists": self.root.exists(),
            "models": len({item["name"] for item in manifests}),
            "versions": len(manifests),
            "artifacts": sum(bool(item.get("has_artifact")) for item in manifests),
            "last_report": deepcopy(self.last_report),
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


model_repository = ModelRepository(settings.AI_MODEL_ROOT)

model_repository_service = model_repository
