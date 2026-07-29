from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.orders.fill_report import FillReport
from app.orders.fill_service import FillService, fill_service
from app.orders.order import Order
from app.orders.order_status import OrderStatus


class MatchingEngine:
    """Fachada legada para confirmações de execução das exchanges.

    O matching engine não modifica a ordem diretamente. Todas as confirmações
    são delegadas ao ``FillService`` e ao ``OrderExecutor`` oficiais.
    """

    def __init__(self, *, service: FillService | None = None) -> None:
        self.service = service if service is not None else fill_service
        self.last_report: dict[str, Any] = {}

    def process_execution(
        self,
        order: Order | str,
        quantity: Any = None,
        price: Any = None,
        fee: Any = 0.0,
        *,
        response: Any = None,
        cumulative: bool | None = None,
        status: Any = None,
        reason: str = "",
        external_id: str | None = None,
    ) -> FillReport | None:
        if isinstance(quantity, Mapping) and response is None:
            response = quantity
            quantity = None

        resolved_order = (
            order
            if isinstance(order, Order)
            else self.service.engine.executor.repository.require(order)
        )

        current = OrderStatus.parse(resolved_order.status)
        if current in {
            OrderStatus.CANCELLED,
            OrderStatus.REJECTED,
            OrderStatus.EXPIRED,
            OrderStatus.FAILED,
        }:
            return None

        report = self.service.process(
            resolved_order,
            quantity,
            price,
            fee,
            response=response,
            cumulative=cumulative,
            status=status,
            reason=reason,
            external_id=external_id,
        )
        self.last_report = report.to_dict()
        return report

    process_fill = process_execution
    execute = process_execution


matching_engine = MatchingEngine()
