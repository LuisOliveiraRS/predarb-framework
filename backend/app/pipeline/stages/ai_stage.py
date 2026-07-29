from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from typing import Any

from app.ai.pipelines.ai_analysis_pipeline import (
    AIAnalysisPipeline,
    ai_analysis_pipeline,
)
from app.pipeline.pipeline_stage import PipelineStage


class AIStage(PipelineStage):
    """
    Estágio consultivo de AI para oportunidades já enriquecidas.

    O estágio somente adiciona ``ai_analysis``. Campos operacionais críticos
    são preservados mesmo quando um serviço de AI customizado é injetado.
    """

    PROTECTED_FIELDS = (
        "approved",
        "executable",
        "execution",
        "portfolio",
        "order",
        "orders",
        "position",
        "positions",
    )

    def __init__(
        self,
        *,
        pipeline: AIAnalysisPipeline | None = None,
        enabled: bool = True,
        strict_features: bool = False,
        fail_on_error: bool = False,
    ) -> None:
        self.pipeline = pipeline or ai_analysis_pipeline
        self.enabled = bool(enabled)
        self.strict_features = bool(strict_features)
        self.fail_on_error = bool(fail_on_error)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _context_metadata(context: Any) -> dict[str, Any]:
        metadata = getattr(context, "metadata", None)
        if isinstance(metadata, dict):
            return metadata

        metadata = {}
        try:
            setattr(context, "metadata", metadata)
        except (AttributeError, TypeError):
            pass
        return metadata

    @staticmethod
    def _context_errors(context: Any) -> list[Any] | None:
        errors = getattr(context, "errors", None)
        return errors if isinstance(errors, list) else None

    @staticmethod
    def _items(context: Any) -> tuple[list[Any], bool]:
        opportunities = getattr(context, "opportunities", None)
        if opportunities is not None:
            if isinstance(opportunities, Mapping):
                return [opportunities], False
            if isinstance(opportunities, (str, bytes)):
                raise TypeError("context.opportunities deve ser uma coleção.")
            try:
                return list(opportunities), False
            except TypeError:
                return [opportunities], False

        opportunity = getattr(context, "opportunity", None)
        if opportunity is None:
            return [], False

        return [opportunity], True

    @classmethod
    def _snapshot(cls, target: Any) -> dict[str, Any]:
        if isinstance(target, Mapping):
            return {
                "kind": "mapping",
                "fields": {
                    field: (
                        field in target,
                        deepcopy(target.get(field)),
                    )
                    for field in cls.PROTECTED_FIELDS
                },
            }

        attributes: dict[str, tuple[bool, Any]] = {}
        for field in cls.PROTECTED_FIELDS:
            exists = hasattr(target, field)
            attributes[field] = (
                exists,
                deepcopy(getattr(target, field, None)) if exists else None,
            )

        metadata = getattr(target, "metadata", None)
        metadata_fields: dict[str, tuple[bool, Any]] = {}
        if isinstance(metadata, Mapping):
            metadata_fields = {
                field: (
                    field in metadata,
                    deepcopy(metadata.get(field)),
                )
                for field in cls.PROTECTED_FIELDS
            }

        return {
            "kind": "object",
            "attributes": attributes,
            "metadata": metadata_fields,
        }

    @classmethod
    def _restore(cls, target: Any, snapshot: dict[str, Any]) -> int:
        restorations = 0

        if snapshot["kind"] == "mapping":
            if not isinstance(target, dict):
                return 0

            for field, (existed, value) in snapshot["fields"].items():
                current_exists = field in target
                current_value = target.get(field)
                changed = current_exists != existed or (
                    existed and current_value != value
                )
                if not changed:
                    continue

                restorations += 1
                if existed:
                    target[field] = deepcopy(value)
                else:
                    target.pop(field, None)
            return restorations

        for field, (existed, value) in snapshot["attributes"].items():
            current_exists = hasattr(target, field)
            current_value = getattr(target, field, None)
            changed = current_exists != existed or (
                existed and current_value != value
            )
            if not changed:
                continue

            restorations += 1
            try:
                if existed:
                    setattr(target, field, deepcopy(value))
                elif current_exists:
                    delattr(target, field)
            except (AttributeError, TypeError):
                pass

        metadata = getattr(target, "metadata", None)
        if isinstance(metadata, dict):
            for field, (existed, value) in snapshot["metadata"].items():
                current_exists = field in metadata
                current_value = metadata.get(field)
                changed = current_exists != existed or (
                    existed and current_value != value
                )
                if not changed:
                    continue

                restorations += 1
                if existed:
                    metadata[field] = deepcopy(value)
                else:
                    metadata.pop(field, None)

        return restorations

    def process(self, context: Any) -> Any:
        metadata = self._context_metadata(context)
        items, singular = self._items(context)

        if not self.enabled:
            self.last_report = {
                "status": "DISABLED",
                "input": len(items),
                "analyzed": 0,
                "advisory_only": True,
                "execution_authorized": False,
            }
            metadata["ai"] = dict(self.last_report)
            return context

        if not items:
            self.last_report = {
                "status": "EMPTY",
                "input": 0,
                "analyzed": 0,
                "advisory_only": True,
                "execution_authorized": False,
            }
            metadata["ai"] = dict(self.last_report)
            return context

        snapshots = [self._snapshot(item) for item in items]

        try:
            analyzed = self.pipeline.analyze(
                items,
                strict_features=self.strict_features,
                copy_results=False,
            )

            if len(analyzed) != len(items):
                raise RuntimeError(
                    "A camada AI alterou a quantidade de oportunidades."
                )

            restorations = sum(
                self._restore(item, snapshot)
                for item, snapshot in zip(analyzed, snapshots)
            )

            if singular:
                setattr(context, "opportunity", analyzed[0])
            else:
                setattr(context, "opportunities", analyzed)

            self.last_report = {
                **dict(self.pipeline.last_report),
                "status": "COMPLETED",
                "input": len(items),
                "analyzed": len(analyzed),
                "operational_restorations": restorations,
                "operational_decisions_changed": False,
                "advisory_only": True,
                "execution_authorized": False,
            }

        except Exception as exc:
            for item, snapshot in zip(items, snapshots):
                self._restore(item, snapshot)

            if self.fail_on_error:
                raise

            self.last_report = {
                "status": "DEGRADED",
                "input": len(items),
                "analyzed": 0,
                "error": str(exc),
                "advisory_only": True,
                "execution_authorized": False,
            }

            errors = self._context_errors(context)
            if errors is not None:
                errors.append(
                    {
                        "stage": self.__class__.__name__,
                        "error": str(exc),
                    }
                )

        metadata["ai"] = dict(self.last_report)
        return context

    def execute(self, context: Any) -> Any:
        """Alias para contratos antigos de PipelineStage."""

        return self.process(context)
