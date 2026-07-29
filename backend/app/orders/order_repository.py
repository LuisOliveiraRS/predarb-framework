from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from app.orders.order_status import OrderStatus


class OrderRepository:
    """Repositório em memória oficial do OMS.

    O repositório é thread-safe e mantém compatibilidade com os nomes
    ``add()``, ``list()`` e ``open_orders()`` usados pelo código antigo.
    """

    def __init__(self) -> None:
        self.orders: dict[str, Any] = {}
        self._lock = RLock()

    @staticmethod
    def _order_id(order: Any) -> str:
        order_id = str(getattr(order, "id", "") or "").strip()
        if not order_id:
            raise ValueError("A ordem deve possuir um ID válido.")
        return order_id

    @staticmethod
    def _status(order: Any) -> OrderStatus | None:
        try:
            return OrderStatus.parse(getattr(order, "status", None))
        except (TypeError, ValueError):
            return None

    def add(self, order: Any, *, replace: bool = True) -> Any:
        order_id = self._order_id(order)
        with self._lock:
            if not replace and order_id in self.orders:
                raise KeyError(f"A ordem {order_id!r} já está registrada.")
            self.orders[order_id] = order
        return order

    save = add
    update = add
    upsert = add

    def add_many(self, orders: Iterable[Any], *, replace: bool = True) -> list[Any]:
        if isinstance(orders, (str, bytes)):
            raise TypeError("orders deve ser uma coleção de ordens.")
        stored: list[Any] = []
        for order in orders:
            stored.append(self.add(order, replace=replace))
        return stored

    save_all = add_many

    def get(self, order_id: Any, default: Any = None) -> Any:
        normalized = str(order_id or "").strip()
        if not normalized:
            return default
        with self._lock:
            return self.orders.get(normalized, default)

    def require(self, order_id: Any) -> Any:
        order = self.get(order_id)
        if order is None:
            raise LookupError(f"Ordem não encontrada: {order_id!r}.")
        return order

    def exists(self, order_id: Any) -> bool:
        normalized = str(order_id or "").strip()
        if not normalized:
            return False
        with self._lock:
            return normalized in self.orders

    def all(self) -> list[Any]:
        with self._lock:
            return list(self.orders.values())

    def list(self) -> list[Any]:
        """Alias legado de :meth:`all`."""
        return self.all()

    def count(self) -> int:
        with self._lock:
            return len(self.orders)

    def remove(self, order_id: Any) -> Any | None:
        normalized = str(order_id or "").strip()
        if not normalized:
            return None
        with self._lock:
            return self.orders.pop(normalized, None)

    pop = remove

    def clear(self) -> None:
        with self._lock:
            self.orders.clear()

    def by_status(self, status: OrderStatus | str) -> list[Any]:
        resolved = OrderStatus.parse(status)
        return [order for order in self.all() if self._status(order) is resolved]

    def by_platform(self, platform: str) -> list[Any]:
        normalized = str(platform or "").strip().casefold()
        if not normalized:
            return []
        return [
            order
            for order in self.all()
            if str(getattr(order, "platform", "") or "").strip().casefold()
            == normalized
        ]

    def by_opportunity(self, opportunity_id: str) -> list[Any]:
        normalized = str(opportunity_id or "").strip()
        if not normalized:
            return []
        return [
            order
            for order in self.all()
            if str(getattr(order, "opportunity_id", "") or "").strip()
            == normalized
        ]

    def open_orders(self) -> list[Any]:
        result: list[Any] = []
        for order in self.all():
            status = self._status(order)
            if status is not None:
                if status.open:
                    result.append(order)
                continue

            completed = getattr(order, "completed", False)
            if callable(completed):
                completed = completed()
            if not bool(completed):
                result.append(order)
        return result

    def terminal_orders(self) -> list[Any]:
        result: list[Any] = []
        for order in self.all():
            status = self._status(order)
            if status is not None and status.terminal:
                result.append(order)
        return result


order_repository = OrderRepository()
