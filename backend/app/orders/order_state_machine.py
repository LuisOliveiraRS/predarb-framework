from __future__ import annotations

from datetime import datetime, timezone
from threading import RLock
from typing import Any, Mapping

from app.orders.order_event import OrderEvent
from app.orders.order_history import OrderHistory, order_history
from app.orders.order_status import OrderStatus


class OrderTransitionError(ValueError):
    """Erro produzido quando uma transição de estado não é permitida."""


class OrderStateMachine:
    """Máquina de estados oficial do OMS.

    A máquina é a única responsável por alterar ``order.status``. Cada
    transição atualiza os timestamps da ordem e registra um evento no
    ``OrderHistory`` oficial.
    """

    TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
        OrderStatus.CREATED: frozenset(
            {
                OrderStatus.VALIDATED,
                # Compatibilidade com o fluxo legado que submetia diretamente.
                OrderStatus.SUBMITTED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.VALIDATED: frozenset(
            {
                OrderStatus.SUBMITTED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.SUBMITTED: frozenset(
            {
                OrderStatus.ACCEPTED,
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.ACCEPTED: frozenset(
            {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
                OrderStatus.EXPIRED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.PARTIALLY_FILLED: frozenset(
            {
                OrderStatus.PARTIALLY_FILLED,
                OrderStatus.FILLED,
                OrderStatus.CANCELLED,
                OrderStatus.EXPIRED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.FAILED: frozenset(
            {
                OrderStatus.RETRYING,
                OrderStatus.CANCELLED,
                OrderStatus.REJECTED,
            }
        ),
        OrderStatus.RETRYING: frozenset(
            {
                OrderStatus.SUBMITTED,
                OrderStatus.CANCELLED,
                OrderStatus.FAILED,
            }
        ),
        OrderStatus.FILLED: frozenset(),
        OrderStatus.CANCELLED: frozenset(),
        OrderStatus.REJECTED: frozenset(),
        OrderStatus.EXPIRED: frozenset(),
    }

    # Nome legado usado em módulos antigos.
    transitions = TRANSITIONS

    def __init__(self, history: OrderHistory | None = None) -> None:
        self.history = history or order_history
        self._lock = RLock()

    @staticmethod
    def _order_id(order: Any) -> str:
        order_id = str(getattr(order, "id", "") or "").strip()
        if not order_id:
            raise ValueError("A ordem deve possuir um ID válido.")
        return order_id

    @staticmethod
    def _current_status(order_or_status: Any) -> OrderStatus:
        if isinstance(order_or_status, (OrderStatus, str)):
            return OrderStatus.parse(order_or_status)
        if order_or_status is None:
            raise ValueError("order não pode ser None.")
        return OrderStatus.parse(getattr(order_or_status, "status", None))

    def allowed_transitions(self, current: Any) -> set[OrderStatus]:
        resolved = self._current_status(current)
        return set(self.TRANSITIONS.get(resolved, frozenset()))

    def can_transition(self, current: Any, new: Any) -> bool:
        current_status = self._current_status(current)
        new_status = OrderStatus.parse(new)
        return new_status in self.TRANSITIONS.get(current_status, frozenset())

    def require_transition(self, current: Any, new: Any) -> None:
        current_status = self._current_status(current)
        new_status = OrderStatus.parse(new)
        if not self.can_transition(current_status, new_status):
            raise OrderTransitionError(
                f"Transição de ordem não permitida: "
                f"{current_status.value} -> {new_status.value}."
            )

    @staticmethod
    def _touch(order: Any, now: datetime) -> None:
        if hasattr(order, "updated_at"):
            order.updated_at = now
        else:
            update_timestamp = getattr(order, "update_timestamp", None)
            if callable(update_timestamp):
                update_timestamp()

    @staticmethod
    def _apply_status_timestamp(order: Any, status: OrderStatus, now: datetime) -> None:
        attributes = {
            OrderStatus.SUBMITTED: "submitted_at",
            OrderStatus.ACCEPTED: "accepted_at",
            OrderStatus.FILLED: "executed_at",
            OrderStatus.CANCELLED: "cancelled_at",
        }
        attribute = attributes.get(status)
        if attribute and hasattr(order, attribute):
            setattr(order, attribute, now)

    @staticmethod
    def _apply_reason(order: Any, status: OrderStatus, reason: str) -> None:
        if not reason:
            return
        if status is OrderStatus.REJECTED and hasattr(order, "reject_reason"):
            order.reject_reason = reason
        elif status is OrderStatus.CANCELLED and hasattr(order, "cancel_reason"):
            order.cancel_reason = reason
        elif status is OrderStatus.FAILED:
            metadata = getattr(order, "metadata", None)
            if isinstance(metadata, dict):
                metadata["failure_reason"] = reason

    def transition(
        self,
        order: Any,
        new_status: OrderStatus | str,
        *,
        reason: str = "",
        details: Mapping[str, Any] | None = None,
        force: bool = False,
    ) -> Any:
        if order is None:
            raise ValueError("order não pode ser None.")

        order_id = self._order_id(order)
        current = self._current_status(order)
        target = OrderStatus.parse(new_status)

        if current is target:
            if current is not OrderStatus.PARTIALLY_FILLED:
                return order
        elif not force:
            self.require_transition(current, target)

        now = datetime.now(timezone.utc)
        normalized_reason = str(reason or "").strip()
        payload = dict(details or {})
        payload.update(
            {
                "from_status": current.value,
                "to_status": target.value,
            }
        )
        if normalized_reason:
            payload["reason"] = normalized_reason

        with self._lock:
            order.status = target
            self._touch(order, now)
            self._apply_status_timestamp(order, target, now)
            self._apply_reason(order, target, normalized_reason)

            if target is OrderStatus.RETRYING and hasattr(order, "retry_count"):
                order.retry_count = int(getattr(order, "retry_count", 0) or 0) + 1

            self.history.add(
                order_id,
                OrderEvent.from_status(target),
                details=payload,
                timestamp=now,
            )

        return order

    move = transition

    def validate(self, order: Any, **kwargs: Any) -> Any:
        return self.transition(order, OrderStatus.VALIDATED, **kwargs)

    def submit(self, order: Any, **kwargs: Any) -> Any:
        return self.transition(order, OrderStatus.SUBMITTED, **kwargs)

    send = submit

    def accept(self, order: Any, **kwargs: Any) -> Any:
        return self.transition(order, OrderStatus.ACCEPTED, **kwargs)

    acknowledge = accept

    def partial_fill(self, order: Any, **kwargs: Any) -> Any:
        return self.transition(order, OrderStatus.PARTIALLY_FILLED, **kwargs)

    def fill(self, order: Any, **kwargs: Any) -> Any:
        return self.transition(order, OrderStatus.FILLED, **kwargs)

    def cancel(self, order: Any, reason: str = "", **kwargs: Any) -> Any:
        return self.transition(
            order,
            OrderStatus.CANCELLED,
            reason=reason,
            **kwargs,
        )

    def reject(self, order: Any, reason: str = "", **kwargs: Any) -> Any:
        return self.transition(
            order,
            OrderStatus.REJECTED,
            reason=reason,
            **kwargs,
        )

    def expire(self, order: Any, reason: str = "", **kwargs: Any) -> Any:
        return self.transition(
            order,
            OrderStatus.EXPIRED,
            reason=reason,
            **kwargs,
        )

    def fail(self, order: Any, reason: str = "", **kwargs: Any) -> Any:
        return self.transition(
            order,
            OrderStatus.FAILED,
            reason=reason,
            **kwargs,
        )

    def retry(self, order: Any, reason: str = "", **kwargs: Any) -> Any:
        return self.transition(
            order,
            OrderStatus.RETRYING,
            reason=reason,
            **kwargs,
        )


order_state_machine = OrderStateMachine()
