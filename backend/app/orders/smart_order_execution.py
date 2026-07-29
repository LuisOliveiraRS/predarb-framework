from __future__ import annotations

from typing import Any

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import ExecutionStrategyPlan
from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.smart_order_router import SmartRoutePlan, smart_order_router
from app.orders.venue_selection.venue import Venue


class SmartOrderExecution:
    """Converte um plano de rota em ordens-filhas CREATED.

    Apesar do nome legado, esta classe não envia ordens e não chama conectores.
    """

    def __init__(self) -> None:
        self.last_plan: ExecutionStrategyPlan | None = None
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _policy(route_plan: SmartRoutePlan) -> ExecutionPolicy:
        return (
            ExecutionPolicy.ADAPTIVE
            if route_plan.routing_mode == "ADAPTIVE"
            else ExecutionPolicy.SMART
        )

    def prepare(
        self,
        order: Order,
        routing: SmartRoutePlan | Venue | Any,
        *,
        allow_partial: bool = False,
    ) -> ExecutionStrategyPlan:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        if isinstance(routing, SmartRoutePlan):
            route_plan = routing
        else:
            venue = Venue.from_value(routing)
            route_plan = smart_order_router.build_plan(
                order,
                venues=[venue],
                require_full_liquidity=not allow_partial,
            )

        if not route_plan.valid:
            raise ValueError("Não existe rota válida para criar o plano de execução.")
        if not route_plan.complete and not allow_partial:
            raise ValueError("A alocação está incompleta; envio não autorizado.")

        policy = self._policy(route_plan)
        mode = f"{policy.value}_PLAN"
        children: list[Order] = []

        for item in route_plan.allocation:
            child = Order(
                platform=item["exchange"],
                market=order.market,
                symbol=order.symbol,
                side=order.side,
                quantity=item["quantity"],
                order_type=order.order_type,
                price=item["price"],
                time_in_force=order.time_in_force,
                opportunity_id=order.opportunity_id,
                leg=order.leg,
                mode=mode,
                execution_policy=policy,
                metadata={
                    **dict(order.metadata),
                    "parent_order_id": order.id,
                    "strategy": policy.value,
                    "route_sequence": item["sequence"],
                    "connector": item["connector"],
                    "planned_notional": item["notional"],
                    "route_score": item.get("route_score", 0.0),
                    "live_execution": False,
                },
            )
            children.append(child)

        batch = OrderBatch(
            children,
            opportunity_id=order.opportunity_id,
            simultaneous=len(children) > 1,
            cancel_on_failure=True,
            metadata={
                "parent_order_id": order.id,
                "strategy": policy.value,
                "route_plan": route_plan.to_dict(),
            },
        )
        plan = ExecutionStrategyPlan(
            policy=policy,
            parent_order=order,
            batch=batch,
            warnings=list(route_plan.warnings),
            metadata={
                "live_execution": False,
                "router": policy.value,
                "route_plan": route_plan.to_dict(),
            },
        )
        if not allow_partial and not plan.valid:
            raise ValueError("O roteador gerou quantidade divergente da ordem-mãe.")

        self.last_plan = plan
        self.last_report = {
            "status": "READY",
            "policy": policy.value,
            "order_id": order.id,
            "child_orders": len(children),
            "total_quantity": plan.total_quantity,
            "live_execution": False,
        }
        return plan

    def execute(self, order: Order, venue: Any) -> ExecutionStrategyPlan:
        """Interface legada segura: prepara, mas não despacha."""

        return self.prepare(order, venue)

    plan = prepare


smart_order_execution = SmartOrderExecution()
