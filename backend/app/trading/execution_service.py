from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.trading.execution_context import ExecutionContext
from app.trading.execution_result import ExecutionResult
from app.trading.trade_executor import TradeExecutor, trade_executor


class ExecutionService:
    """Interface pública para executar uma ordem ou coleção de ordens."""

    def __init__(self, executor: TradeExecutor | None = None) -> None:
        self.executor = executor or trade_executor
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(values: Any) -> list[Any]:
        if values is None:
            return []
        if isinstance(values, (ExecutionContext, Mapping)):
            return [values]
        if isinstance(values, (str, bytes)):
            raise TypeError("values deve conter ordens ou contextos de execução.")
        if isinstance(values, Iterable):
            return list(values)
        return [values]

    def execute_one(
        self,
        value: Any,
        venue: Any = None,
        **kwargs: Any,
    ) -> ExecutionResult:
        if isinstance(value, ExecutionContext):
            if venue is not None:
                value.venue = venue
            return self.executor.execute_context(value, **kwargs)

        return self.executor.execute(value, venue, **kwargs)

    def execute(
        self,
        values: Any,
        venue: Any = None,
        *,
        stop_on_failure: bool = False,
        **kwargs: Any,
    ) -> list[ExecutionResult]:
        items = self._as_list(values)
        results: list[ExecutionResult] = []

        for item in items:
            result = self.execute_one(item, venue, **kwargs)
            results.append(result)
            if stop_on_failure and not result.success:
                break

        self.last_report = {
            "input": len(items),
            "returned": len(results),
            "successful": sum(1 for result in results if result.success),
            "failed": sum(1 for result in results if not result.success),
            "stopped_early": len(results) < len(items),
            "live_enabled": self.executor.enabled,
        }
        return results

    run = execute

    def status(self) -> dict[str, Any]:
        return {
            "executor": self.executor.status(),
            "last_report": dict(self.last_report),
        }


execution_service = ExecutionService()
