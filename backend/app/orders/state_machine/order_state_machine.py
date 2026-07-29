"""Fachada do pacote legado ``app.orders.state_machine``."""

from app.orders.order_state_machine import (
    OrderStateMachine,
    OrderTransitionError,
    order_state_machine,
)


state_machine = order_state_machine


__all__ = [
    "OrderStateMachine",
    "OrderTransitionError",
    "order_state_machine",
    "state_machine",
]
