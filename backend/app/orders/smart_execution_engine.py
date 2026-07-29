from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.orders.ai_router.adaptive_router import AdaptiveRouter
from app.orders.ai_router.adaptive_selector import AdaptiveSelector
from app.orders.ai_router.execution_history import ExecutionHistory, execution_history
from app.orders.ai_router.router_statistics import RouterStatistics, router_statistics
from app.orders.execution_strategy import ExecutionStrategyPlan
from app.orders.order import Order
from app.orders.smart_order_execution import SmartOrderExecution, smart_order_execution
from app.orders.smart_order_router import SmartOrderRouter, SmartRoutePlan, smart_order_router


@dataclass(slots=True)
class SmartExecutionResult:
    status: str
    order: Order
    route_plan: SmartRoutePlan
    execution_plan: ExecutionStrategyPlan | None = None
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def success(self) -> bool:
        return self.status == "READY" and self.execution_plan is not None

    @property
    def executed(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "success": self.success,
            "executed": False,
            "reason": self.reason,
            "order_id": self.order.id,
            "route_plan": self.route_plan.to_dict(),
            "execution_plan": self.execution_plan.to_dict() if self.execution_plan else None,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


class SmartExecutionEngine:
    """Orquestrador de planejamento SMART/ADAPTIVE.

    A gravação de resultados históricos é explícita por ``record_execution``.
    Planejar uma rota nunca é tratado como execução bem-sucedida.
    """

    def __init__(
        self,
        *,
        router: SmartOrderRouter | None = None,
        planner: SmartOrderExecution | None = None,
        history: ExecutionHistory | None = None,
        statistics: RouterStatistics | None = None,
    ) -> None:
        self.history = history if history is not None else execution_history
        if router is not None:
            self.router = router
        elif history is not None:
            self.router = SmartOrderRouter(
                adaptive_selector_service=AdaptiveSelector(
                    router=AdaptiveRouter(history=self.history)
                )
            )
        else:
            self.router = smart_order_router
        self.planner = planner if planner is not None else smart_order_execution
        self.statistics = (
            statistics
            if statistics is not None
            else (
                RouterStatistics(history=self.history)
                if history is not None
                else router_statistics
            )
        )
        self.last_result: SmartExecutionResult | None = None

    def plan(
        self,
        order: Order,
        venues: Iterable[Any] | None = None,
        *,
        liquidity_levels: Iterable[Any] | None = None,
        require_full_liquidity: bool = True,
        max_venues: int | None = None,
        adaptive: bool = False,
    ) -> SmartExecutionResult:
        route_plan = self.router.build_plan(
            order,
            venues,
            liquidity_levels=liquidity_levels,
            require_full_liquidity=require_full_liquidity,
            max_venues=max_venues,
            adaptive=adaptive,
        )
        routing_mode = "ADAPTIVE" if adaptive else "SMART"

        if not route_plan.valid:
            result = SmartExecutionResult(
                status="REJECTED",
                order=order,
                route_plan=route_plan,
                reason="NO_ELIGIBLE_ROUTE",
                metadata={"live_execution": False, "routing_mode": routing_mode},
            )
        elif require_full_liquidity and not route_plan.complete:
            result = SmartExecutionResult(
                status="REJECTED",
                order=order,
                route_plan=route_plan,
                reason="INSUFFICIENT_LIQUIDITY",
                metadata={"live_execution": False, "routing_mode": routing_mode},
            )
        else:
            execution_plan = self.planner.prepare(
                order,
                route_plan,
                allow_partial=not require_full_liquidity,
            )
            result = SmartExecutionResult(
                status="READY",
                order=order,
                route_plan=route_plan,
                execution_plan=execution_plan,
                reason="OK",
                metadata={
                    "live_execution": False,
                    "routing_mode": routing_mode,
                    "next_step": "SUBMIT_PLAN_TO_OMS",
                },
            )

        self.last_result = result
        return result

    def execute(
        self,
        order: Order,
        venues: Iterable[Any] | None = None,
        **options: Any,
    ) -> SmartExecutionResult:
        """Interface legada segura: gera plano e nunca envia à exchange."""

        return self.plan(order, venues, **options)

    def record_execution(self, venue: Any, report: Any | None = None) -> Any:
        """Registra somente um relatório real já produzido pelo OMS."""

        return self.history.add(venue, report)

    record = record_execution

    def clear_learning(self, venue: Any | None = None) -> None:
        self.history.clear(venue)

    def status(self) -> dict[str, Any]:
        return {
            "live_execution": False,
            "learning": self.statistics.summary(),
            "last_result": self.last_result.to_dict() if self.last_result else None,
        }


smart_execution_engine = SmartExecutionEngine()
