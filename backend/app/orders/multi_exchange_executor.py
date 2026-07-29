from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any

from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.order_batch_executor import OrderBatchExecutor, order_batch_executor
from app.orders.order_batch_report import OrderBatchReport
from app.orders.order_manager import OrderManager, order_manager
from app.orders.order_status import OrderStatus


class MultiExchangeExecutor:
    """Divide uma ordem em ordens-filhas e as envia a múltiplas venues.

    O método não altera a quantidade preenchida da ordem-mãe. Confirmações de
    fill das ordens-filhas continuam sendo processadas pelo ``OrderExecutor``.
    """

    def __init__(
        self,
        *,
        batch_executor: OrderBatchExecutor | None = None,
        manager: OrderManager | None = None,
        enabled: bool = False,
    ) -> None:
        self.batch_executor = (
            batch_executor if batch_executor is not None else order_batch_executor
        )
        self.manager = manager if manager is not None else order_manager
        self.enabled = bool(enabled)
        self.last_report: dict[str, Any] = {}

    @staticmethod
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

    @staticmethod
    def _allocation_items(allocation: Any) -> list[Mapping[str, Any]]:
        if isinstance(allocation, Mapping):
            items = [allocation]
        elif isinstance(allocation, (str, bytes)):
            raise TypeError("allocation deve ser uma coleção de alocações.")
        elif isinstance(allocation, Iterable):
            items = list(allocation)
        else:
            raise TypeError("allocation deve ser uma coleção de alocações.")

        if not items:
            raise ValueError("allocation não pode ser vazia.")
        if not all(isinstance(item, Mapping) for item in items):
            raise TypeError("Cada alocação deve ser um Mapping.")
        return items

    @classmethod
    def _child_order(
        cls,
        parent: Order,
        item: Mapping[str, Any],
        index: int,
    ) -> Order:
        platform = str(
            item.get("platform", item.get("exchange", "")) or ""
        ).strip()
        if not platform:
            raise ValueError("Cada alocação deve informar exchange ou platform.")

        quantity = cls._positive_number(item.get("quantity"), "quantity")
        price = item.get("price", parent.price)
        price_value = float(price or 0.0)

        metadata = dict(parent.metadata or {})
        metadata.update(dict(item.get("metadata", {}) or {}))
        metadata.update(
            {
                "parent_order_id": parent.id,
                "allocation_index": index,
                "source": "multi_exchange_executor",
            }
        )

        return Order(
            platform=platform,
            market=parent.market,
            symbol=parent.symbol,
            side=parent.side,
            quantity=quantity,
            price=price_value,
            order_type=parent.order_type,
            time_in_force=parent.time_in_force,
            status=OrderStatus.CREATED,
            opportunity_id=parent.opportunity_id,
            leg=parent.leg,
            mode="MULTI_EXCHANGE",
            execution_policy=parent.execution_policy,
            metadata=metadata,
        )

    def build_batch(
        self,
        order: Order,
        allocation: Any,
        *,
        simultaneous: bool = True,
        cancel_on_failure: bool = True,
    ) -> OrderBatch:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        items = self._allocation_items(allocation)
        children = [
            self._child_order(order, item, index)
            for index, item in enumerate(items)
        ]

        allocated_quantity = sum(child.quantity for child in children)
        available_quantity = order.remaining_quantity
        if allocated_quantity > available_quantity + 1e-8:
            raise ValueError(
                "A quantidade alocada excede a quantidade disponível da ordem."
            )

        return OrderBatch(
            children,
            opportunity_id=order.opportunity_id,
            simultaneous=simultaneous,
            cancel_on_failure=cancel_on_failure,
            metadata={
                "parent_order_id": order.id,
                "allocated_quantity": round(allocated_quantity, 8),
                "unallocated_quantity": round(
                    max(0.0, available_quantity - allocated_quantity),
                    8,
                ),
            },
        )

    def _register_and_submit(self, batch: OrderBatch) -> None:
        for child in batch:
            if self.manager.get(child.id) is None:
                self.manager.register(child)
            status = OrderStatus.parse(child.status)
            if status in {OrderStatus.CREATED, OrderStatus.VALIDATED}:
                self.manager.submit(child)
            elif status is not OrderStatus.SUBMITTED:
                raise ValueError(
                    f"Ordem-filha {child.id} não pode ser submetida em "
                    f"estado {status.value}."
                )

    def execute(
        self,
        order: Order,
        allocation: Any,
        *,
        enabled: bool | None = None,
        simultaneous: bool = True,
        cancel_on_failure: bool = True,
        canceller: Any = None,
    ) -> OrderBatchReport:
        batch = self.build_batch(
            order,
            allocation,
            simultaneous=simultaneous,
            cancel_on_failure=cancel_on_failure,
        )
        resolved_enabled = self.enabled if enabled is None else bool(enabled)

        if resolved_enabled:
            self._register_and_submit(batch)

        report = self.batch_executor.execute(
            batch,
            enabled=resolved_enabled,
            simultaneous=simultaneous,
            cancel_on_failure=cancel_on_failure,
            canceller=canceller,
        )
        report.metadata.update(
            {
                "parent_order_id": order.id,
                "allocated_quantity": batch.metadata["allocated_quantity"],
                "unallocated_quantity": batch.metadata["unallocated_quantity"],
            }
        )
        self.last_report = report.to_dict()
        return report

    def execute_responses(self, order: Order, allocation: Any, **kwargs: Any) -> list[Any]:
        """Interface legada que retorna somente as respostas individuais."""

        return self.execute(order, allocation, **kwargs).to_list()


multi_exchange_executor = MultiExchangeExecutor()
