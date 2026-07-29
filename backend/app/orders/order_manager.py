from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.order_event import OrderEvent
from app.orders.order_builder import OrderBuilder, order_builder
from app.orders.order_lifecycle import OrderLifecycle, order_lifecycle
from app.orders.order_queue import OrderQueue, order_queue
from app.orders.order_repository import OrderRepository, order_repository
from app.orders.order_response import OrderResponse
from app.orders.order_status import OrderStatus
from app.orders.order_validator import OrderValidator, order_validator


class OrderManager:
    """Serviço central do OMS para criação e ciclo de vida de ordens.

    O Manager não envia ordens reais automaticamente. ``dispatch`` exige
    habilitação explícita e o roteamento permanece delegado ao Dispatcher.
    Planos das camadas Execution, SMART e ADAPTIVE são somente convertidos e
    registrados; submissão e despacho são etapas separadas.
    """

    def __init__(
        self,
        *,
        builder: OrderBuilder | None = None,
        validator: OrderValidator | None = None,
        lifecycle: OrderLifecycle | None = None,
        repository: OrderRepository | None = None,
        queue: OrderQueue | None = None,
        dispatcher: Any = None,
        dispatch_enabled: bool = False,
    ) -> None:
        self.builder = builder if builder is not None else order_builder
        self.validator = validator if validator is not None else order_validator
        self.lifecycle = lifecycle if lifecycle is not None else order_lifecycle
        self.repository = (
            repository if repository is not None else order_repository
        )
        self.queue = queue if queue is not None else order_queue
        self.dispatcher = dispatcher
        self.dispatch_enabled = bool(dispatch_enabled)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_orders(value: Any) -> list[Order]:
        if value is None:
            return []
        if isinstance(value, Order):
            return [value]
        if isinstance(value, OrderBatch):
            orders = value.all()
        elif isinstance(value, Mapping):
            orders = list(value.values())
        elif isinstance(value, (str, bytes)):
            raise TypeError("orders deve ser uma ordem ou coleção de ordens.")
        elif isinstance(value, Iterable):
            orders = list(value)
        else:
            orders = [value]

        if not all(isinstance(order, Order) for order in orders):
            raise TypeError("A coleção contém um item que não é Order.")
        return orders

    def register(self, order: Order, *, replace: bool = True) -> Order:
        self.validator.validate_or_raise(order)
        stored = self.repository.add(order, replace=replace)
        history = self.lifecycle.state_machine.history
        if history.count(order.id) == 0:
            history.add(
                order.id,
                OrderEvent.CREATED,
                details={
                    "status": OrderStatus.parse(order.status).value,
                    "source": "order_manager",
                },
                timestamp=order.created_at,
            )
        return stored

    def register_batch(
        self,
        batch: OrderBatch,
        *,
        require_created: bool = False,
        replace: bool = True,
    ) -> OrderBatch:
        if not isinstance(batch, OrderBatch):
            raise TypeError("batch deve ser uma instância de OrderBatch.")

        batch.validate_or_raise()
        orders = batch.all()

        if require_created:
            invalid = [
                order.id
                for order in orders
                if OrderStatus.parse(order.status) is not OrderStatus.CREATED
                or order.filled_quantity > 0
            ]
            if invalid:
                raise ValueError(
                    "Planos somente podem registrar ordens CREATED e sem fills: "
                    + ", ".join(invalid)
                )

        for order in orders:
            self.validator.validate_or_raise(order)

        for order in orders:
            self.register(order, replace=replace)

        self.last_report = {
            "operation": "register_batch",
            "batch_id": batch.id,
            "orders": len(orders),
            "order_ids": [order.id for order in orders],
            "opportunity_id": batch.opportunity_id,
            "submitted": batch.submitted,
            "live_execution": False,
        }
        return batch

    def create(self, **kwargs: Any) -> Order:
        order = self.builder.build_order(**kwargs)
        return self.register(order)

    def create_from_intent(self, intent: Mapping[str, Any]) -> Order:
        order = self.builder.build_from_intent(intent)
        return self.register(order)

    def create_pair(self, opportunity: Any) -> dict[str, Order]:
        pair = self.builder.build_pair(opportunity)
        for order in pair.values():
            self.register(order)
        return pair

    def create_from_execution_plan(
        self,
        plan: Any,
        *,
        require_approved: bool = True,
    ) -> OrderBatch:
        batch = self.builder.build_from_execution_plan(
            plan,
            require_approved=require_approved,
        )
        self.register_batch(batch, require_created=True)
        self.last_report = {
            **self.last_report,
            "operation": "create_from_execution_plan",
            "approved": self.builder.execution_plan_approved(plan),
        }
        return batch

    create_execution_batch = create_from_execution_plan

    def create_from_strategy_plan(self, plan: Any) -> OrderBatch:
        batch = getattr(plan, "batch", None)
        valid = getattr(plan, "valid", None)

        if not isinstance(batch, OrderBatch):
            raise TypeError(
                "plan deve ser um ExecutionStrategyPlan com atributo batch."
            )
        if valid is not None and not bool(valid):
            raise ValueError("O ExecutionStrategyPlan não está válido.")

        self.register_batch(batch, require_created=True)
        policy = getattr(getattr(plan, "policy", None), "value", None)
        self.last_report = {
            **self.last_report,
            "operation": "create_from_strategy_plan",
            "policy": policy,
        }
        return batch

    create_strategy_plan_batch = create_from_strategy_plan

    def create_from_smart_result(self, result: Any) -> OrderBatch:
        execution_plan = getattr(result, "execution_plan", None)
        success = getattr(result, "success", None)

        if success is not None and not bool(success):
            reason = str(getattr(result, "reason", "SMART_PLAN_REJECTED") or "SMART_PLAN_REJECTED")
            raise ValueError(f"O planejamento SMART/ADAPTIVE foi rejeitado: {reason}.")
        if execution_plan is None:
            raise ValueError("O resultado SMART/ADAPTIVE não possui execution_plan.")

        batch = self.create_from_strategy_plan(execution_plan)
        self.last_report = {
            **self.last_report,
            "operation": "create_from_smart_result",
            "routing_mode": getattr(
                getattr(execution_plan, "policy", None),
                "value",
                None,
            ),
        }
        return batch

    def create_strategy_batch(
        self,
        order: Order,
        policy: Any = None,
        **options: Any,
    ) -> OrderBatch:
        from app.orders.execution_strategy_factory import execution_strategy_factory

        plan = execution_strategy_factory.plan(order, policy, **options)
        return self.create_from_strategy_plan(plan)

    def create_batch(self, value: Any) -> OrderBatch:
        """Converte e registra um lote a partir dos contratos oficiais."""

        if isinstance(value, OrderBatch):
            return self.register_batch(value)

        if self.builder.is_execution_plan(value):
            return self.create_from_execution_plan(value)

        execution_plan = getattr(value, "execution_plan", None)
        if execution_plan is not None:
            return self.create_from_smart_result(value)

        batch = getattr(value, "batch", None)
        if isinstance(batch, OrderBatch):
            return self.create_from_strategy_plan(value)

        orders = self._as_orders(value)
        resolved_batch = OrderBatch(orders)
        return self.register_batch(resolved_batch)

    def create_many(self, orders: Any) -> list[Order]:
        items = self._as_orders(orders)
        for order in items:
            self.register(order)
        return items

    def _register_built(self, built: Any) -> Any:
        if isinstance(built, Order):
            return self.register(built)
        if isinstance(built, OrderBatch):
            return self.register_batch(built, require_created=True)
        if isinstance(built, Mapping):
            orders = self._as_orders(built)
            for order in orders:
                self.register(order)
            return built
        raise TypeError("O OrderBuilder retornou um contrato não suportado.")

    # Alias legado usado por versões antigas do Pipeline.
    def create_orders(self, value: Any) -> Any:
        if isinstance(value, Iterable) and not isinstance(
            value, (str, bytes, Mapping, Order, OrderBatch)
        ):
            return [self._register_built(self.builder.build(item)) for item in value]
        return self._register_built(self.builder.build(value))

    def validate(self, order: Order) -> Order:
        self.validator.validate_or_raise(order)
        status = OrderStatus.parse(order.status)
        if status is OrderStatus.CREATED:
            self.lifecycle.validate(order)
        return self.repository.add(order)

    def submit(self, order: Order) -> Order:
        self.validator.validate_or_raise(order)
        if self.repository.get(order.id) is None:
            self.register(order)
        status = OrderStatus.parse(order.status)
        if status is OrderStatus.CREATED:
            self.lifecycle.validate(order)
            status = OrderStatus.VALIDATED
        if status in {OrderStatus.VALIDATED, OrderStatus.RETRYING}:
            self.lifecycle.submit(order)
        elif status is not OrderStatus.SUBMITTED:
            raise ValueError(
                f"Somente ordens CREATED ou VALIDATED podem ser submetidas; "
                f"estado atual: {status.value}."
            )
        self.repository.add(order)
        self.queue.push(order)
        self.last_report = {
            "operation": "submit",
            "order_id": order.id,
            "status": order.status.value,
            "queued": self.queue.contains(order.id),
        }
        return order

    def submit_many(self, orders: Any) -> list[Order]:
        return [self.submit(order) for order in self._as_orders(orders)]

    def submit_batch(self, batch: OrderBatch) -> OrderBatch:
        if not isinstance(batch, OrderBatch):
            raise TypeError("batch deve ser uma instância de OrderBatch.")
        batch.validate_or_raise()

        allowed = {
            OrderStatus.CREATED,
            OrderStatus.VALIDATED,
            OrderStatus.RETRYING,
            OrderStatus.SUBMITTED,
        }
        invalid = [
            f"{order.id}:{OrderStatus.parse(order.status).value}"
            for order in batch
            if OrderStatus.parse(order.status) not in allowed
        ]
        if invalid:
            raise ValueError(
                "O lote contém ordens que não podem ser submetidas: "
                + ", ".join(invalid)
            )

        for order in batch:
            self.validator.validate_or_raise(order)

        for order in batch:
            self.submit(order)

        self.last_report = {
            "operation": "submit_batch",
            "batch_id": batch.id,
            "orders": len(batch),
            "submitted": batch.submitted,
            "queued": sum(1 for order in batch if self.queue.contains(order.id)),
        }
        return batch

    def dispatch(
        self,
        order: Order,
        *,
        enabled: bool | None = None,
    ) -> OrderResponse:
        resolved_enabled = self.dispatch_enabled if enabled is None else bool(enabled)
        if not resolved_enabled:
            self.last_report = {
                "operation": "dispatch",
                "order_id": order.id,
                "status": "DISABLED",
                "dispatched": False,
            }
            return OrderResponse.disabled(order)

        status = OrderStatus.parse(order.status)
        if status in {OrderStatus.CREATED, OrderStatus.VALIDATED}:
            self.submit(order)
        elif status is not OrderStatus.SUBMITTED:
            raise ValueError(
                f"A ordem deve estar SUBMITTED antes do despacho; "
                f"estado atual: {status.value}."
            )

        dispatcher = self.dispatcher
        if dispatcher is None:
            # Import tardio para manter o núcleo do OMS desacoplado dos conectores.
            from app.orders.order_dispatcher import order_dispatcher

            dispatcher = order_dispatcher

        raw_response = dispatcher.dispatch(order)
        response = (
            raw_response
            if isinstance(raw_response, OrderResponse)
            else OrderResponse(order, raw_response)
        )
        self.last_report = {
            "operation": "dispatch",
            "order_id": order.id,
            "status": response.status,
            "dispatched": bool(response.success or response.accepted),
            "accepted": response.accepted,
            "error": response.error,
        }
        return response

    def plan_smart(
        self,
        order: Order,
        venues: Any = None,
        *,
        adaptive: bool = False,
        **options: Any,
    ) -> Any:
        from app.orders.smart_execution_engine import smart_execution_engine

        return smart_execution_engine.plan(
            order,
            venues,
            adaptive=adaptive,
            **options,
        )

    def smart_execute(
        self,
        order: Order,
        *,
        enabled: bool = False,
        venues: Any = None,
        adaptive: bool = False,
        **options: Any,
    ) -> Any:
        """Interface legada segura.

        Mesmo com ``enabled=True``, o SmartExecutionEngine apenas gera plano.
        O retorno sempre informa ``executed=False``.
        """

        if not enabled:
            return {
                "status": "DISABLED",
                "executed": False,
                "reason": "SMART_EXECUTION_DISABLED",
                "order_id": order.id,
            }

        return self.plan_smart(
            order,
            venues,
            adaptive=adaptive,
            **options,
        )

    def fill(
        self,
        order_id: Any,
        quantity: Any,
        price: Any,
        fee: Any = 0.0,
    ) -> Order | None:
        order = self.repository.get(order_id)
        if order is None:
            return None
        self.lifecycle.apply_fill(order, quantity, price, fee=fee)
        self.repository.add(order)
        if order.status.terminal:
            self.queue.remove(order.id)
        self.last_report = {
            "operation": "fill",
            "order_id": order.id,
            "status": order.status.value,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": order.remaining_quantity,
        }
        return order

    def accept(self, order: Order) -> Order:
        self.lifecycle.accept(order)
        return self.repository.add(order)

    acknowledge = accept

    def cancel(self, order: Order, reason: str = "") -> Order:
        self.lifecycle.cancel(order, reason=reason)
        self.queue.remove(order.id)
        return self.repository.add(order)

    def reject(self, order: Order, reason: str = "") -> Order:
        self.lifecycle.reject(order, reason=reason)
        self.queue.remove(order.id)
        return self.repository.add(order)

    def expire(self, order: Order, reason: str = "") -> Order:
        self.lifecycle.expire(order, reason=reason)
        self.queue.remove(order.id)
        return self.repository.add(order)

    def fail(self, order: Order, reason: str = "") -> Order:
        self.lifecycle.fail(order, reason=reason)
        self.queue.remove(order.id)
        return self.repository.add(order)

    def retry(self, order: Order, reason: str = "") -> Order:
        self.lifecycle.retry(order, reason=reason)
        self.repository.add(order)
        return self.submit(order)

    def get(self, order_id: Any, default: Any = None) -> Order | Any:
        return self.repository.get(order_id, default)

    def require(self, order_id: Any) -> Order:
        return self.repository.require(order_id)

    def all(self) -> list[Order]:
        return self.repository.all()

    def pending(self) -> list[Order]:
        return self.repository.open_orders()

    open_orders = pending

    def by_status(self, status: OrderStatus | str) -> list[Order]:
        return self.repository.by_status(status)

    def by_opportunity(self, opportunity_id: str) -> list[Order]:
        return self.repository.by_opportunity(opportunity_id)

    def remove(self, order_id: Any) -> Order | None:
        self.queue.remove(order_id)
        return self.repository.remove(order_id)

    def clear(self) -> None:
        self.queue.clear()
        self.repository.clear()
        self.last_report = {}

    def status(self) -> dict[str, Any]:
        return {
            "orders": self.repository.count(),
            "open_orders": len(self.repository.open_orders()),
            "queued": self.queue.size(),
            "dispatch_enabled": self.dispatch_enabled,
            "dispatcher_configured": self.dispatcher is not None,
            "last_report": dict(self.last_report),
        }


order_manager = OrderManager()
