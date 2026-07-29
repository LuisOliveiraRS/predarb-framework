from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.orders.order import Order
from app.orders.order_dispatcher import OrderDispatcher, order_dispatcher
from app.orders.order_response import OrderResponse


class OrderSender:
    """Interface de envio utilizada por lotes e integrações legadas."""

    def __init__(self, *, dispatcher: OrderDispatcher | None = None) -> None:
        self.dispatcher = dispatcher if dispatcher is not None else order_dispatcher
        self.last_responses: list[OrderResponse] = []

    @staticmethod
    def _as_orders(value: Any) -> list[Order]:
        if isinstance(value, Order):
            return [value]
        if isinstance(value, Mapping):
            items = list(value.values())
        elif isinstance(value, (str, bytes)):
            raise TypeError("orders deve ser uma ordem ou coleção de ordens.")
        elif isinstance(value, Iterable):
            items = list(value)
        else:
            items = [value]
        if not all(isinstance(item, Order) for item in items):
            raise TypeError("A coleção contém um item que não é Order.")
        return items

    def send(
        self,
        order: Order,
        *,
        connector: Any = None,
        raise_on_error: bool = False,
    ) -> OrderResponse:
        response = self.dispatcher.dispatch(
            order,
            connector=connector,
            raise_on_error=raise_on_error,
        )
        self.last_responses = [response]
        return response

    def send_many(
        self,
        orders: Any,
        *,
        stop_on_error: bool = False,
    ) -> list[OrderResponse]:
        responses: list[OrderResponse] = []
        for order in self._as_orders(orders):
            response = self.send(order)
            responses.append(response)
            if stop_on_error and not response.success:
                break
        self.last_responses = responses
        return responses


order_sender = OrderSender()
