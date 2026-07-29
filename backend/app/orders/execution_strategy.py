from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.orders.execution_policy import ExecutionPolicy
from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.order_type import OrderType
from app.orders.time_in_force import TimeInForce


def _positive_number(value: Any, field_name: str) -> float:
    if isinstance(value, bool):
        raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc
    if not isfinite(number) or number <= 0:
        raise ValueError(
            f"O campo {field_name!r} deve ser finito e maior que zero."
        )
    return number


def allocate_quantities(total: Any, weights: list[Any]) -> list[float]:
    """Distribui quantidade preservando exatamente o total na última fatia."""

    resolved_total = _positive_number(total, "total")
    if not weights:
        raise ValueError("weights não pode ser vazio.")

    parsed = [_positive_number(weight, "weight") for weight in weights]
    weight_sum = sum(parsed)
    quantities: list[float] = []
    allocated = 0.0

    for index, weight in enumerate(parsed):
        if index == len(parsed) - 1:
            quantity = round(resolved_total - allocated, 8)
        else:
            quantity = round(resolved_total * weight / weight_sum, 8)
            allocated = round(allocated + quantity, 8)
        quantities.append(quantity)

    if any(quantity <= 0 for quantity in quantities):
        raise ValueError("A distribuição gerou uma fatia sem quantidade positiva.")
    return quantities


@dataclass(slots=True)
class ExecutionStrategyPlan:
    """Plano imutável do ponto de vista operacional.

    O plano contém ordens-filhas em estado CREATED. Nenhuma exchange é chamada.
    """

    policy: ExecutionPolicy
    parent_order: Order
    batch: OrderBatch
    schedule: list[dict[str, Any]] = field(default_factory=list)
    reports: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    @property
    def orders(self) -> list[Order]:
        return self.batch.all()

    @property
    def total_quantity(self) -> float:
        return round(sum(order.quantity for order in self.batch), 8)

    @property
    def parent_quantity(self) -> float:
        return round(self.parent_order.remaining_quantity, 8)

    @property
    def valid(self) -> bool:
        return (
            bool(self.batch)
            and self.batch.evaluate()["valid"]
            and abs(self.total_quantity - self.parent_quantity) <= 1e-8
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "policy": self.policy.value,
            "parent_order_id": self.parent_order.id,
            "valid": self.valid,
            "total_quantity": self.total_quantity,
            "parent_quantity": self.parent_quantity,
            "orders": [order.to_dict() for order in self.batch],
            "schedule": [dict(item) for item in self.schedule],
            "reports": list(self.reports),
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True)
class ExecutionStrategyContext:
    order: Order
    policy: ExecutionPolicy
    options: dict[str, Any] = field(default_factory=dict)
    child_orders: list[Order] = field(default_factory=list)
    schedule: list[dict[str, Any]] = field(default_factory=list)
    execution_reports: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not isinstance(self.order, Order):
            raise TypeError("order deve ser uma instância de Order.")
        self.policy = ExecutionPolicy.parse(self.policy)
        self.options = dict(self.options or {})
        self.metadata = dict(self.metadata or {})

    def add_order(self, order: Order, *, execute_at: datetime | None = None) -> Order:
        if not isinstance(order, Order):
            raise TypeError("A estratégia tentou adicionar um item que não é Order.")
        self.child_orders.append(order)
        if execute_at is not None:
            if execute_at.tzinfo is None:
                execute_at = execute_at.replace(tzinfo=timezone.utc)
            self.schedule.append(
                {
                    "order_id": order.id,
                    "sequence": len(self.child_orders),
                    "execute_at": execute_at.isoformat(),
                }
            )
        return order

    def to_plan(self) -> ExecutionStrategyPlan:
        batch = OrderBatch(
            self.child_orders,
            opportunity_id=self.order.opportunity_id,
            simultaneous=bool(self.options.get("simultaneous", False)),
            cancel_on_failure=bool(self.options.get("cancel_on_failure", True)),
            metadata={
                "parent_order_id": self.order.id,
                "strategy": self.policy.value,
                **self.metadata,
            },
        )
        return ExecutionStrategyPlan(
            policy=self.policy,
            parent_order=self.order,
            batch=batch,
            schedule=list(self.schedule),
            reports=list(self.execution_reports),
            warnings=list(self.warnings),
            metadata={
                "live_execution": False,
                "parent_order_id": self.order.id,
                **self.metadata,
            },
        )


class ExecutionStrategy(ABC):
    """Contrato oficial das estratégias de planejamento do OMS."""

    policy = ExecutionPolicy.LIMIT

    def __init__(self, *, policy: ExecutionPolicy | str | None = None) -> None:
        self.policy = ExecutionPolicy.parse(policy or self.policy)
        self.last_plan: ExecutionStrategyPlan | None = None

    @staticmethod
    def _context(
        value: ExecutionStrategyContext | Order,
        policy: ExecutionPolicy,
        options: Mapping[str, Any] | None = None,
    ) -> ExecutionStrategyContext:
        if isinstance(value, ExecutionStrategyContext):
            value.policy = policy
            if options:
                value.options.update(dict(options))
            return value
        if isinstance(value, Order):
            return ExecutionStrategyContext(
                order=value,
                policy=policy,
                options=dict(options or {}),
            )
        raise TypeError("A estratégia exige Order ou ExecutionStrategyContext.")

    def execute(
        self,
        context: ExecutionStrategyContext | Order,
        **options: Any,
    ) -> ExecutionStrategyContext:
        """Interface legada segura: gera o contexto, sem enviar ordens."""

        resolved = self._context(context, self.policy, options)
        resolved.child_orders.clear()
        resolved.schedule.clear()
        resolved.execution_reports.clear()
        resolved.warnings.clear()
        self._build(resolved)
        plan = resolved.to_plan()
        if not plan.valid:
            raise ValueError(
                "A estratégia gerou um plano inválido ou com quantidade divergente."
            )
        self.last_plan = plan
        return resolved

    def plan(self, order: Order, **options: Any) -> ExecutionStrategyPlan:
        context = self.execute(order, **options)
        assert self.last_plan is not None
        return self.last_plan

    build = plan

    @abstractmethod
    def _build(self, context: ExecutionStrategyContext) -> None:
        raise NotImplementedError

    def _child(
        self,
        context: ExecutionStrategyContext,
        *,
        quantity: Any,
        sequence: int,
        platform: str | None = None,
        market: str | None = None,
        symbol: str | None = None,
        price: Any | None = None,
        order_type: OrderType | str | None = None,
        time_in_force: TimeInForce | str | None = None,
        execute_at: datetime | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Order:
        parent = context.order
        child_metadata = {
            **dict(parent.metadata),
            "parent_order_id": parent.id,
            "strategy": context.policy.value,
            "sequence": int(sequence),
            **dict(metadata or {}),
        }
        if execute_at is not None:
            normalized = (
                execute_at
                if execute_at.tzinfo is not None
                else execute_at.replace(tzinfo=timezone.utc)
            )
            child_metadata["execute_at"] = normalized.isoformat()

        child = Order(
            platform=str(platform or parent.platform).strip(),
            market=str(market or parent.market).strip(),
            symbol=str(symbol or parent.symbol).strip(),
            side=parent.side,
            quantity=quantity,
            order_type=order_type or parent.order_type,
            price=parent.price if price is None else price,
            time_in_force=time_in_force or parent.time_in_force,
            opportunity_id=parent.opportunity_id,
            leg=parent.leg,
            mode="STRATEGY_PLAN",
            execution_policy=context.policy,
            metadata=child_metadata,
        )
        return context.add_order(child, execute_at=execute_at)
