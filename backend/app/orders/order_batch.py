from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.orders.order import Order
from app.orders.order_status import OrderStatus


class OrderBatch:
    """Coleção identificável de ordens coordenadas pelo OMS.

    A classe preserva a interface legada ``add()``, ``all()`` e ``clear()``,
    mas impede IDs duplicados e sempre devolve cópias da lista interna.
    """

    def __init__(
        self,
        orders: Iterable[Order] | Mapping[str, Order] | None = None,
        *,
        batch_id: str | None = None,
        id: str | None = None,
        opportunity_id: str = "",
        simultaneous: bool = True,
        cancel_on_failure: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        self.id = str(batch_id or id or uuid4()).strip()
        self.opportunity_id = str(opportunity_id or "").strip()
        self.simultaneous = bool(simultaneous)
        self.cancel_on_failure = bool(cancel_on_failure)
        self.metadata = dict(metadata or {})
        self.created_at = datetime.now(timezone.utc)

        self.orders: list[Order] = []
        self._order_ids: set[str] = set()

        if orders is not None:
            self.add_many(orders)

        if not self.opportunity_id:
            ids = {
                order.opportunity_id
                for order in self.orders
                if str(order.opportunity_id or "").strip()
            }
            if len(ids) == 1:
                self.opportunity_id = ids.pop()

    @staticmethod
    def _normalize_orders(
        value: Iterable[Order] | Mapping[str, Order],
    ) -> list[Order]:
        if isinstance(value, Mapping):
            items = list(value.values())
        elif isinstance(value, (str, bytes)):
            raise TypeError("orders deve ser uma coleção de objetos Order.")
        else:
            items = list(value)

        if not all(isinstance(item, Order) for item in items):
            raise TypeError("O lote contém um item que não é Order.")

        return items

    def add(
        self,
        order: Order,
        *,
        allow_duplicate: bool = False,
    ) -> Order:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        if order.id in self._order_ids and not allow_duplicate:
            return order

        self.orders.append(order)
        self._order_ids.add(order.id)
        return order

    append = add

    def add_many(
        self,
        orders: Iterable[Order] | Mapping[str, Order],
        *,
        allow_duplicate: bool = False,
    ) -> list[Order]:
        added: list[Order] = []
        for order in self._normalize_orders(orders):
            previous_size = len(self.orders)
            self.add(order, allow_duplicate=allow_duplicate)
            if len(self.orders) > previous_size:
                added.append(order)
        return added

    extend = add_many

    def get(self, order_id: Any, default: Any = None) -> Order | Any:
        normalized = str(order_id or "").strip()
        if not normalized:
            return default
        for order in self.orders:
            if order.id == normalized:
                return order
        return default

    def remove(self, order_or_id: Any) -> Order | None:
        target_id = str(getattr(order_or_id, "id", order_or_id) or "").strip()
        if not target_id:
            return None

        for index, order in enumerate(self.orders):
            if order.id == target_id:
                removed = self.orders.pop(index)
                if not any(item.id == target_id for item in self.orders):
                    self._order_ids.discard(target_id)
                return removed
        return None

    def all(self) -> list[Order]:
        return list(self.orders)

    list = all

    def clear(self) -> None:
        self.orders.clear()
        self._order_ids.clear()

    def size(self) -> int:
        return len(self.orders)

    count = size

    @property
    def legs(self) -> dict[str, list[Order]]:
        grouped: dict[str, list[Order]] = {}
        for order in self.orders:
            leg = str(order.leg or "UNSPECIFIED").strip().upper()
            grouped.setdefault(leg, []).append(order)
        return grouped

    @property
    def submitted(self) -> bool:
        return bool(self.orders) and all(
            OrderStatus.parse(order.status) is OrderStatus.SUBMITTED
            for order in self.orders
        )

    @property
    def terminal(self) -> bool:
        return bool(self.orders) and all(
            OrderStatus.parse(order.status).terminal
            for order in self.orders
        )

    def evaluate(self) -> dict[str, Any]:
        errors: list[str] = []
        warnings: list[str] = []

        if not self.orders:
            errors.append("BATCH_EMPTY")

        platforms = [str(order.platform or "").strip() for order in self.orders]
        if any(not platform for platform in platforms):
            errors.append("PLATFORM_MISSING")

        if len(self._order_ids) != len(self.orders):
            errors.append("DUPLICATE_ORDER_ID")

        opportunity_ids = {
            str(order.opportunity_id or "").strip()
            for order in self.orders
            if str(order.opportunity_id or "").strip()
        }
        if len(opportunity_ids) > 1:
            warnings.append("MULTIPLE_OPPORTUNITIES")

        if self.opportunity_id and opportunity_ids and self.opportunity_id not in opportunity_ids:
            warnings.append("BATCH_OPPORTUNITY_MISMATCH")

        return {
            "valid": not errors,
            "errors": errors,
            "warnings": warnings,
            "orders": len(self.orders),
            "platforms": platforms,
            "legs": {
                leg: len(orders)
                for leg, orders in self.legs.items()
            },
        }

    def validate_or_raise(self) -> "OrderBatch":
        report = self.evaluate()
        if not report["valid"]:
            raise ValueError("Lote inválido: " + ", ".join(report["errors"]))
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "opportunity_id": self.opportunity_id,
            "simultaneous": self.simultaneous,
            "cancel_on_failure": self.cancel_on_failure,
            "orders": [order.to_dict() for order in self.orders],
            "count": len(self.orders),
            "evaluation": self.evaluate(),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    def __iter__(self) -> Iterator[Order]:
        return iter(self.all())

    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return bool(self.orders)

    def __getitem__(self, index: int) -> Order:
        return self.orders[index]
