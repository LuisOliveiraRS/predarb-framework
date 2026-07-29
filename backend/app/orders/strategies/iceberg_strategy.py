from __future__ import annotations

from math import ceil

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import ExecutionStrategy, ExecutionStrategyContext


class IcebergStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.ICEBERG

    def _build(self, context: ExecutionStrategyContext) -> None:
        visible = float(
            context.options.get("visible_quantity", context.order.visible_quantity)
        )
        total = context.order.remaining_quantity
        if visible <= 0:
            raise ValueError("visible_quantity deve ser maior que zero.")
        visible = min(visible, total)
        slices = int(ceil(total / visible))
        remaining = total

        for sequence in range(1, slices + 1):
            quantity = round(min(visible, remaining), 8)
            remaining = round(max(0.0, remaining - quantity), 8)
            self._child(
                context,
                quantity=quantity,
                sequence=sequence,
                metadata={
                    "visible_quantity": visible,
                    "release_after_previous": sequence > 1,
                    "hidden_remaining_after": remaining,
                },
            )

        context.metadata.update(
            visible_quantity=visible,
            slices=slices,
            sequential_release=True,
        )
        context.execution_reports.append(f"ICEBERG_PLAN_GENERATED:{slices}")
