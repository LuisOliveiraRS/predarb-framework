from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.order_metrics import OrderMetrics, order_metrics
from app.orders.order_repository import OrderRepository, order_repository


class OrderStatistics:
    """Fachada única para métricas do repositório ou de uma coleção informada."""

    def __init__(
        self,
        *,
        repository: OrderRepository | None = None,
        metrics: OrderMetrics | None = None,
    ) -> None:
        self.repository = repository or order_repository
        self.metrics = metrics or order_metrics
        self.last_report: dict[str, Any] = {}

    def calculate(self, orders: Iterable[Any] | None = None) -> dict[str, Any]:
        source = self.repository.all() if orders is None else orders
        report = self.metrics.calculate(source)
        self.last_report = dict(report)
        return report

    def summary(self, orders: Iterable[Any] | None = None) -> dict[str, Any]:
        return self.calculate(orders)

    snapshot = summary

    def reset(self) -> None:
        self.last_report = {}


order_statistics = OrderStatistics()
