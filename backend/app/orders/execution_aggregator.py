from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.execution_report import ExecutionReport


class ExecutionAggregator:
    """Agrega fragmentos de execução de uma mesma ordem."""

    def aggregate(
        self,
        order: Any,
        executions: Iterable[Any] | None,
    ) -> ExecutionReport:
        report = ExecutionReport(order)
        for execution in list(executions or []):
            report.add(execution)
        return report.finalize()

    def aggregate_one(self, order: Any, execution: Any) -> ExecutionReport:
        return self.aggregate(order, [execution])


execution_aggregator = ExecutionAggregator()
