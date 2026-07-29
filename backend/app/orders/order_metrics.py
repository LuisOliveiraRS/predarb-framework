from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any

from app.orders.order_status import OrderStatus


class OrderMetrics:
    """Calcula métricas determinísticas para uma coleção de ordens."""

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        value = getattr(target, field_name, default)
        return value() if callable(value) else value

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return float(default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if isfinite(number) else float(default)

    @classmethod
    def _status(cls, order: Any) -> OrderStatus | None:
        try:
            return OrderStatus.parse(cls._read(order, "status", None))
        except (TypeError, ValueError):
            return None

    def calculate(self, orders: Iterable[Any] | None) -> dict[str, Any]:
        if orders is None:
            items: list[Any] = []
        elif isinstance(orders, (str, bytes, Mapping)):
            raise TypeError("orders deve ser uma coleção de ordens.")
        else:
            items = list(orders)

        status_counter: Counter[str] = Counter()
        unknown_status = 0
        total_quantity = 0.0
        filled_quantity = 0.0
        total_notional = 0.0
        filled_notional = 0.0
        fees_paid = 0.0
        weighted_fill_value = 0.0

        for order in items:
            status = self._status(order)
            if status is None:
                unknown_status += 1
            else:
                status_counter[status.value] += 1

            quantity = max(0.0, self._number(self._read(order, "quantity", 0.0)))
            filled = max(
                0.0,
                min(quantity, self._number(self._read(order, "filled_quantity", 0.0))),
            )
            price = max(0.0, self._number(self._read(order, "price", 0.0)))
            average_price = max(
                0.0,
                self._number(self._read(order, "average_price", 0.0)),
            )

            total_quantity += quantity
            filled_quantity += filled
            total_notional += quantity * price
            filled_notional += filled * average_price
            weighted_fill_value += filled * average_price
            fees_paid += max(0.0, self._number(self._read(order, "fees_paid", 0.0)))

        total = len(items)
        filled = status_counter[OrderStatus.FILLED.value]
        partial = status_counter[OrderStatus.PARTIALLY_FILLED.value]
        cancelled = status_counter[OrderStatus.CANCELLED.value]
        rejected = status_counter[OrderStatus.REJECTED.value]
        expired = status_counter[OrderStatus.EXPIRED.value]
        failed = status_counter[OrderStatus.FAILED.value]
        terminal = filled + cancelled + rejected + expired + failed
        open_orders = total - terminal

        fill_rate = filled_quantity / total_quantity if total_quantity > 0 else 0.0
        completion_rate = filled / total if total > 0 else 0.0
        rejection_rate = rejected / total if total > 0 else 0.0
        cancellation_rate = cancelled / total if total > 0 else 0.0
        average_fill_price = (
            weighted_fill_value / filled_quantity if filled_quantity > 0 else 0.0
        )

        return {
            "total": total,
            "created": status_counter[OrderStatus.CREATED.value],
            "validated": status_counter[OrderStatus.VALIDATED.value],
            "submitted": status_counter[OrderStatus.SUBMITTED.value],
            "accepted": status_counter[OrderStatus.ACCEPTED.value],
            "retrying": status_counter[OrderStatus.RETRYING.value],
            "filled": filled,
            "partial": partial,
            "partially_filled": partial,
            "cancelled": cancelled,
            "rejected": rejected,
            "expired": expired,
            "failed": failed,
            "open": open_orders,
            "terminal": terminal,
            "unknown_status": unknown_status,
            "fill_rate": round(fill_rate, 6),
            "fill_rate_percentage": round(fill_rate * 100, 2),
            "completion_rate": round(completion_rate, 6),
            "completion_rate_percentage": round(completion_rate * 100, 2),
            "rejection_rate": round(rejection_rate, 6),
            "cancellation_rate": round(cancellation_rate, 6),
            "total_quantity": round(total_quantity, 8),
            "filled_quantity": round(filled_quantity, 8),
            "remaining_quantity": round(max(0.0, total_quantity - filled_quantity), 8),
            "total_notional": round(total_notional, 8),
            "filled_notional": round(filled_notional, 8),
            "average_fill_price": round(average_fill_price, 8),
            "fees_paid": round(fees_paid, 8),
            "statuses": dict(sorted(status_counter.items())),
        }

    summary = calculate


order_metrics = OrderMetrics()
