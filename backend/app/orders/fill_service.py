from __future__ import annotations

from typing import Any

from app.orders.fill_engine import FillEngine, fill_engine
from app.orders.fill_report import FillReport
from app.orders.fill_repository import FillRepository, fill_repository
from app.orders.order import Order


class FillService:
    """Serviço oficial de aplicação e persistência de fills."""

    def __init__(
        self,
        *,
        engine: FillEngine | None = None,
        repository: FillRepository | None = None,
    ) -> None:
        self.engine = engine if engine is not None else fill_engine
        self.repository = repository if repository is not None else fill_repository
        self.last_report: dict[str, Any] = {}

    def process(
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
    ) -> FillReport:
        report = self.engine.process_fill(
            order,
            quantity,
            price,
            fee,
            response=response,
            cumulative=cumulative,
            status=status,
            reason=reason,
            external_id=external_id,
        )

        if report.success and report.fill is not None:
            self.repository.add(report.fill)

        self.last_report = report.to_dict()
        return report

    process_fill = process

    def process_response(
        self,
        order: Order | str,
        response: Any,
        *,
        cumulative: bool | None = None,
        reason: str = "",
    ) -> FillReport:
        return self.process(
            order,
            response=response,
            cumulative=cumulative,
            reason=reason,
        )

    def all(self):
        return self.repository.all()

    def by_order(self, order_id: Any):
        return self.repository.by_order(order_id)

    def clear(self, order_id: Any | None = None) -> None:
        self.repository.clear(order_id)


fill_service = FillService()
