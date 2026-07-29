from __future__ import annotations

from math import isfinite
from typing import Any

from app.orders.order_state_machine import (
    OrderStateMachine,
    order_state_machine,
)
from app.orders.order_status import OrderStatus


class OrderLifecycle:
    """Operações oficiais do ciclo de vida de uma ordem.

    A classe atualiza quantidades/preços de fills e delega toda alteração
    de status à máquina de estados oficial.
    """

    def __init__(self, state_machine: OrderStateMachine | None = None) -> None:
        self.state_machine = state_machine or order_state_machine

    @staticmethod
    def _number(value: Any, field_name: str, *, positive: bool = False) -> float:
        if isinstance(value, bool):
            raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc
        if not isfinite(number):
            raise ValueError(f"O campo {field_name!r} deve ser finito.")
        if positive and number <= 0:
            raise ValueError(f"O campo {field_name!r} deve ser maior que zero.")
        if not positive and number < 0:
            raise ValueError(f"O campo {field_name!r} não pode ser negativo.")
        return number

    @staticmethod
    def _status(order: Any) -> OrderStatus:
        if order is None:
            raise ValueError("order não pode ser None.")
        return OrderStatus.parse(getattr(order, "status", None))

    def validate(self, order: Any) -> Any:
        return self.state_machine.validate(order)

    def submit(self, order: Any) -> Any:
        current = self._status(order)
        if current is OrderStatus.CREATED:
            self.validate(order)
        return self.state_machine.submit(order)

    send = submit

    def accept(self, order: Any) -> Any:
        return self.state_machine.accept(order)

    acknowledge = accept

    def apply_fill(
        self,
        order: Any,
        quantity: Any,
        price: Any,
        *,
        fee: Any = 0.0,
    ) -> Any:
        fill_quantity = self._number(quantity, "quantity", positive=True)
        fill_price = self._number(price, "price", positive=True)
        fill_fee = self._number(fee, "fee")

        current = self._status(order)
        if current.terminal:
            raise ValueError(
                f"Não é possível preencher uma ordem em estado {current.value}."
            )

        total_quantity = self._number(
            getattr(order, "quantity", None),
            "order.quantity",
            positive=True,
        )
        current_filled = self._number(
            getattr(order, "filled_quantity", 0.0),
            "order.filled_quantity",
        )
        remaining = max(0.0, total_quantity - current_filled)
        if remaining <= 0:
            raise ValueError("A ordem não possui quantidade remanescente.")

        applied_quantity = min(fill_quantity, remaining)
        previous_average = self._number(
            getattr(order, "average_price", 0.0),
            "order.average_price",
        )
        previous_value = previous_average * current_filled
        new_filled = current_filled + applied_quantity
        new_average = (previous_value + fill_price * applied_quantity) / new_filled

        order.filled_quantity = round(new_filled, 8)
        order.average_price = round(new_average, 8)
        order.last_fill_price = fill_price
        order.last_fill_quantity = round(applied_quantity, 8)
        order.fees_paid = round(
            self._number(getattr(order, "fees_paid", 0.0), "order.fees_paid")
            + fill_fee,
            8,
        )

        target = (
            OrderStatus.FILLED
            if order.filled_quantity >= total_quantity
            else OrderStatus.PARTIALLY_FILLED
        )
        details = {
            "fill_quantity": round(applied_quantity, 8),
            "fill_price": fill_price,
            "average_price": order.average_price,
            "filled_quantity": order.filled_quantity,
            "remaining_quantity": round(max(0.0, total_quantity - new_filled), 8),
            "fee": fill_fee,
        }

        if target is OrderStatus.FILLED:
            self.state_machine.fill(order, details=details)
        else:
            self.state_machine.partial_fill(order, details=details)

        # A máquina atualiza o timestamp geral; este campo é específico do fill.
        order.last_fill_time = getattr(order, "updated_at", None)
        return order

    def partial_fill(
        self,
        order: Any,
        quantity: Any,
        average_price: Any,
        fee: Any = 0.0,
    ) -> Any:
        return self.apply_fill(
            order,
            quantity,
            average_price,
            fee=fee,
        )

    def fill(
        self,
        order: Any,
        average_price: Any,
        quantity: Any | None = None,
        fee: Any = 0.0,
    ) -> Any:
        remaining = getattr(order, "remaining_quantity", None)
        if callable(remaining):
            remaining = remaining()
        if remaining is None:
            remaining = float(order.quantity) - float(order.filled_quantity)
        applied_quantity = remaining if quantity is None else quantity
        return self.apply_fill(
            order,
            applied_quantity,
            average_price,
            fee=fee,
        )

    def cancel(self, order: Any, reason: str = "") -> Any:
        return self.state_machine.cancel(order, reason=reason)

    def reject(self, order: Any, reason: str = "") -> Any:
        return self.state_machine.reject(order, reason=reason)

    def expire(self, order: Any, reason: str = "") -> Any:
        return self.state_machine.expire(order, reason=reason)

    def fail(self, order: Any, reason: str = "") -> Any:
        return self.state_machine.fail(order, reason=reason)

    def retry(self, order: Any, reason: str = "") -> Any:
        return self.state_machine.retry(order, reason=reason)


order_lifecycle = OrderLifecycle()
