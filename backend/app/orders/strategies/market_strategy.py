from __future__ import annotations

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import ExecutionStrategy, ExecutionStrategyContext
from app.orders.order_type import OrderType
from app.orders.time_in_force import TimeInForce


class MarketStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.MARKET

    def _build(self, context: ExecutionStrategyContext) -> None:
        self._child(
            context,
            quantity=context.order.remaining_quantity,
            sequence=1,
            order_type=OrderType.MARKET,
            time_in_force=context.options.get("time_in_force", TimeInForce.IOC),
            metadata={"reference_price": context.order.price},
        )
        context.execution_reports.append("MARKET_PLAN_GENERATED")
