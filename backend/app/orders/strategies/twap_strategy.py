from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    allocate_quantities,
)


class TWAPStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.TWAP

    def _build(self, context: ExecutionStrategyContext) -> None:
        slices = context.options.get("slices", context.order.twap_slices)
        interval = context.options.get("interval", context.order.twap_interval)
        start_at = context.options.get("start_at") or datetime.now(timezone.utc)

        if isinstance(slices, bool):
            raise TypeError("slices deve ser inteiro.")
        slices = int(slices)
        interval = float(interval)
        if slices <= 0:
            raise ValueError("slices deve ser maior que zero.")
        if interval < 0:
            raise ValueError("interval não pode ser negativo.")
        if not isinstance(start_at, datetime):
            raise TypeError("start_at deve ser datetime.")
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)

        quantities = allocate_quantities(
            context.order.remaining_quantity,
            [1.0] * slices,
        )
        for index, quantity in enumerate(quantities):
            execute_at = start_at + timedelta(seconds=index * interval)
            self._child(
                context,
                quantity=quantity,
                sequence=index + 1,
                execute_at=execute_at,
                metadata={"interval_seconds": interval},
            )

        context.metadata.update(
            slices=slices,
            interval_seconds=interval,
            scheduled=True,
        )
        context.execution_reports.append(f"TWAP_PLAN_GENERATED:{slices}")
