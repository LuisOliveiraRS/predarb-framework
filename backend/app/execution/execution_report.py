from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from app.execution.execution_plan import (
    ExecutionPlan,
)


class ExecutionReport:
    """
    Cria relatórios de planejamento e agrega
    resultados de execução.

    Mantém compatibilidade com:

        execution_report.create(plan)

    e:

        report = ExecutionReport()
        report.add(item)
    """

    def __init__(self) -> None:
        self._items: list[Any] = []

    def create(
        self,
        plan: ExecutionPlan,
        *,
        status: str | None = None,
        mode: str = "PLAN",
        result: Any = None,
        error: str | None = None,
    ) -> dict[str, Any]:
        if not isinstance(
            plan,
            ExecutionPlan,
        ):
            raise TypeError(
                "plan deve ser uma instância "
                "de ExecutionPlan."
            )

        resolved_status = (
            status
            or (
                "READY"
                if plan.execute
                else "REJECTED"
            )
        )

        return {
            "status": str(
                resolved_status
            ).strip().upper(),
            "mode": str(
                mode
            ).strip().upper(),
            "approved": plan.approved,
            "execute": plan.execute,
            "reason": plan.reason,
            "latency_limit": (
                plan.max_latency
            ),
            "simultaneous": (
                plan.simultaneous
            ),
            "retry": plan.retry,
            "cancel_on_failure": (
                plan.cancel_on_failure
            ),
            "expected_profit": (
                plan.expected_profit
            ),
            "estimated_roi": (
                plan.estimated_roi
            ),
            "plan": plan.to_dict(),
            "result": result,
            "error": error,
            "created_at": datetime.now(
                timezone.utc
            ).isoformat(),
        }

    def add(
        self,
        item: Any,
    ) -> Any:
        self._items.append(
            item
        )

        return item

    def all(self) -> list[Any]:
        return list(
            self._items
        )

    def clear(self) -> None:
        self._items.clear()

    def to_dict(self) -> dict[str, Any]:
        return {
            "items": self.all(),
            "count": len(
                self._items
            ),
        }


execution_report = ExecutionReport()