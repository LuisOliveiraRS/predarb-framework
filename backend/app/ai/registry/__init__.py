"""API pública lazy do registro de modelos."""

from __future__ import annotations

from importlib import import_module
from typing import Any


_EXPORTS = {
    "ModelRegistry": ("app.ai.registry.model_registry", "ModelRegistry"),
    "model_registry_service": (
        "app.ai.registry.model_registry",
        "model_registry_service",
    ),
    "ModelLifecycleService": (
        "app.ai.registry.model_lifecycle",
        "ModelLifecycleService",
    ),
    "model_lifecycle_service": (
        "app.ai.registry.model_lifecycle",
        "model_lifecycle_service",
    ),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str) -> Any:
    try:
        module_name, attribute_name = _EXPORTS[name]
    except KeyError as exc:
        raise AttributeError(
            f"module 'app.ai.registry' has no attribute {name!r}"
        ) from exc

    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value


def __dir__() -> list[str]:
    return sorted(set(globals()) | set(__all__))
