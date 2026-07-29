from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.trading.execution_context import ExecutionContext
from app.trading.execution_pipeline import ExecutionPipeline, execution_pipeline
from app.trading.execution_result import ExecutionResult


class TradeExecutor:
    """Fachada oficial para iniciar uma execução da camada Trading."""

    def __init__(
        self,
        *,
        pipeline: ExecutionPipeline | None = None,
        executor: Any = None,
        enabled: bool = False,
    ) -> None:
        self.pipeline = pipeline or execution_pipeline
        self.executor = executor
        self.enabled = bool(enabled)
        self.last_result: ExecutionResult | None = None

    def configure(
        self,
        *,
        executor: Any = None,
        enabled: bool | None = None,
    ) -> None:
        if executor is not None:
            self.executor = executor
        if enabled is not None:
            self.enabled = bool(enabled)

    def disable(self) -> None:
        self.enabled = False

    def execute_context(
        self,
        context: ExecutionContext,
        **kwargs: Any,
    ) -> ExecutionResult:
        if not isinstance(context, ExecutionContext):
            raise TypeError("context deve ser uma instância de ExecutionContext.")

        kwargs.setdefault(
            "enabled",
            True if context.live_enabled else self.enabled,
        )
        kwargs.setdefault("executor", self.executor)
        result = self.pipeline.execute(context, **kwargs)
        self.last_result = result
        return result

    def execute(
        self,
        order: Any,
        venue: Any = None,
        *,
        context: ExecutionContext | None = None,
        enabled: bool | None = None,
        executor: Any = None,
        metadata: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExecutionResult:
        resolved_enabled = self.enabled if enabled is None else bool(enabled)
        resolved_context = context or ExecutionContext(
            order,
            venue,
            metadata=metadata,
            live_enabled=resolved_enabled,
        )

        if context is not None:
            if order is not None and context.order is not order:
                raise ValueError("order diverge da ordem armazenada no contexto.")
            if venue is not None:
                context.venue = venue
            if metadata:
                context.metadata.update(dict(metadata))
            context.live_enabled = resolved_enabled

        result = self.pipeline.execute(
            resolved_context,
            enabled=resolved_enabled,
            executor=executor or self.executor,
            **kwargs,
        )
        self.last_result = result
        return result

    run = execute

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "executor_configured": self.executor is not None,
            "pipeline": self.pipeline.status(),
            "last_result": (
                self.last_result.to_dict()
                if self.last_result is not None
                else None
            ),
        }


trade_executor = TradeExecutor()
