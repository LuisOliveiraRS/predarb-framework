from __future__ import annotations

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    allocate_quantities,
)


class SplitStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.SPLIT

    def _build(self, context: ExecutionStrategyContext) -> None:
        parts = context.options.get("parts", context.order.split_parts)
        if isinstance(parts, bool):
            raise TypeError("parts deve ser inteiro.")
        parts = int(parts)
        if parts <= 0:
            raise ValueError("parts deve ser maior que zero.")

        quantities = allocate_quantities(
            context.order.remaining_quantity,
            [1.0] * parts,
        )
        for sequence, quantity in enumerate(quantities, start=1):
            self._child(
                context,
                quantity=quantity,
                sequence=sequence,
                metadata={"parts": parts},
            )
        context.metadata["parts"] = parts
        context.execution_reports.append(f"SPLIT_PLAN_GENERATED:{parts}")
