from __future__ import annotations

from typing import Any

from app.orders.order_repository import OrderRepository, order_repository


class OrderTracker:
    """Fachada de rastreamento sobre o repositório oficial de ordens.

    A implementação anterior mantinha um segundo dicionário independente,
    permitindo divergência entre tracker e repository. Agora ambos usam a
    mesma fonte de verdade.
    """

    def __init__(self, repository: OrderRepository | None = None) -> None:
        self.repository = repository or order_repository

    @property
    def orders(self) -> dict[str, Any]:
        """Mapa somente para compatibilidade com código legado."""
        return {order.id: order for order in self.repository.all()}

    def register(self, order: Any) -> Any:
        return self.repository.add(order)

    add = register

    def get(self, order_id: Any, default: Any = None) -> Any:
        return self.repository.get(order_id, default)

    def require(self, order_id: Any) -> Any:
        return self.repository.require(order_id)

    def update(self, order: Any) -> Any:
        return self.repository.add(order)

    def remove(self, order_id: Any) -> Any | None:
        return self.repository.remove(order_id)

    def all(self) -> list[Any]:
        return self.repository.all()

    list = all

    def open(self) -> list[Any]:
        return self.repository.open_orders()

    open_orders = open

    def clear(self) -> None:
        self.repository.clear()

    def count(self) -> int:
        return self.repository.count()


order_tracker = OrderTracker()
