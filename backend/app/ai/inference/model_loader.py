from __future__ import annotations

from copy import deepcopy
from inspect import signature
from typing import Any, Callable

from app.ai.model_repository import ModelRepository, model_repository
from app.ai.models.model_metadata import ModelMetadata


class ModelLoader:
    """
    Loader explícito e opt-in de artefatos.

    Não existe desserializador padrão. O chamador precisa fornecer uma função
    de carregamento e confirmar que confia no artefato. Antes da chamada, o
    checksum e o tamanho são verificados pelo repositório.
    """

    def __init__(self, repository: ModelRepository | None = None) -> None:
        self.repository = repository or model_repository
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _invoke(
        loader: Callable[..., Any],
        path: Any,
        metadata: ModelMetadata,
    ) -> Any:
        try:
            parameters = signature(loader).parameters
            positional = [
                parameter
                for parameter in parameters.values()
                if parameter.kind.name in {
                    "POSITIONAL_ONLY",
                    "POSITIONAL_OR_KEYWORD",
                }
            ]
            accepts_varargs = any(
                parameter.kind.name == "VAR_POSITIONAL"
                for parameter in parameters.values()
            )
        except (TypeError, ValueError):
            positional = []
            accepts_varargs = True

        if accepts_varargs or len(positional) >= 2:
            return loader(path, metadata)
        return loader(path)

    def load(
        self,
        name: str,
        version: str,
        *,
        loader: Callable[..., Any] | None,
        trusted: bool = False,
        expected_serializer: str | None = None,
    ) -> tuple[Any, ModelMetadata]:
        if loader is None or not callable(loader):
            raise TypeError("Um loader explícito e chamável é obrigatório.")
        if not trusted:
            raise PermissionError("MODEL_ARTIFACT_TRUST_REQUIRED")

        metadata = self.repository.read_metadata(name, version)
        if not metadata.has_artifact:
            raise FileNotFoundError("MODEL_ARTIFACT_NOT_REGISTERED")
        if not metadata.trusted_artifact:
            raise PermissionError("MODEL_ARTIFACT_NOT_MARKED_TRUSTED")
        if (
            expected_serializer is not None
            and metadata.serializer != str(expected_serializer)
        ):
            raise ValueError("MODEL_SERIALIZER_MISMATCH")

        # Força a verificação de checksum e tamanho antes da desserialização.
        self.repository.read_artifact_bytes(name, version, verify=True)
        path = self.repository.artifact_path(name, version, metadata=metadata)
        model = self._invoke(loader, path, metadata)
        if model is None:
            raise ValueError("MODEL_LOADER_RETURNED_NONE")

        self.last_report = {
            "operation": "LOAD",
            "name": metadata.name,
            "version": metadata.version,
            "path": str(path),
            "serializer": metadata.serializer,
            "checksum_verified": True,
            "trusted": True,
        }
        return model, metadata

    def status(self) -> dict[str, Any]:
        return {
            "repository": self.repository.status(),
            "last_report": deepcopy(self.last_report),
            "default_loader": None,
            "auto_load": False,
            "advisory_only": True,
            "execution_authorized": False,
        }


model_loader = ModelLoader()

model_loader_service = model_loader
