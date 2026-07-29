from __future__ import annotations

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import ExecutionStrategy, ExecutionStrategyContext
from app.orders.order_type import OrderType
from app.orders.time_in_force import TimeInForce


class LimitStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.LIMIT

    def _build(self, context: ExecutionStrategyContext) -> None:
        if context.order.price <= 0:
            raise ValueError("A estratégia LIMIT exige preço maior que zero.")

        time_in_force = context.options.get("time_in_force", context.order.time_in_force)
        post_only = False
        if context.policy is ExecutionPolicy.IOC:
            time_in_force = TimeInForce.IOC
        elif context.policy is ExecutionPolicy.FOK:
            time_in_force = TimeInForce.FOK
        elif context.policy is ExecutionPolicy.POST_ONLY:
            time_in_force = TimeInForce.GTC
            post_only = True

        self._child(
            context,
            quantity=context.order.remaining_quantity,
            sequence=1,
            order_type=OrderType.LIMIT,
            time_in_force=time_in_force,
            metadata={"post_only": post_only},
        )
        context.execution_reports.append(f"{context.policy.value}_PLAN_GENERATED")
