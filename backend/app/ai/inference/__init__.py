"""API pública lazy da camada de inferência."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "InferenceService": (
        "app.ai.inference.inference_service",
        "InferenceService",
    ),
    "inference_service_instance": (
        "app.ai.inference.inference_service",
        "inference_service_instance",
    ),
    "ModelLoader": ("app.ai.inference.model_loader", "ModelLoader"),
    "model_loader_service": (
        "app.ai.inference.model_loader",
        "model_loader_service",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module 'app.ai.inference' has no attribute {name!r}"
        ) from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
