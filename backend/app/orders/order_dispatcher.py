from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.orders.order import Order
from app.orders.order_lifecycle import OrderLifecycle, order_lifecycle
from app.orders.order_queue import OrderQueue, order_queue
from app.orders.order_repository import OrderRepository, order_repository
from app.orders.order_response import OrderResponse
from app.orders.order_router import OrderRouter, order_router
from app.orders.order_status import OrderStatus
from app.orders.order_validator import OrderValidator, order_validator


class OrderDispatcher:
    """Despacha uma ordem submetida e normaliza a resposta do conector.

    O Dispatcher pode reconhecer aceitação, rejeição, cancelamento ou falha.
    Quantidades executadas nunca são aplicadas aqui: qualquer fill recebido na
    resposta deve ser processado pelo ``OrderExecutor`` oficial.
    """

    ACCEPTED_STATUSES = {
        "SUCCESS",
        "OK",
        "ACCEPTED",
        "ACKNOWLEDGED",
        "SUBMITTED",
        "OPEN",
        "PARTIALLY_FILLED",
        "PARTIAL_FILL",
        "FILLED",
        "COMPLETED",
    }
    REJECTED_STATUSES = {"REJECTED", "DECLINED"}
    CANCELLED_STATUSES = {"CANCELLED", "CANCELED"}
    FAILED_STATUSES = {"FAILED", "ERROR"}

    def __init__(
        self,
        *,
        router: OrderRouter | None = None,
        validator: OrderValidator | None = None,
        lifecycle: OrderLifecycle | None = None,
        repository: OrderRepository | None = None,
        queue: OrderQueue | None = None,
    ) -> None:
        self.router = router if router is not None else order_router
        self.validator = validator if validator is not None else order_validator
        self.lifecycle = lifecycle if lifecycle is not None else order_lifecycle
        self.repository = repository if repository is not None else order_repository
        self.queue = queue if queue is not None else order_queue
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @classmethod
    def _broker_status(cls, response: Any) -> str:
        status = cls._read(response, "status", cls._read(response, "state", ""))
        value = getattr(status, "value", status)
        return str(value or "").strip().upper()

    @classmethod
    def _has_fill(cls, response: Any) -> bool:
        for field_name in (
            "fill",
            "fills",
            "filled_quantity",
            "executed_quantity",
            "last_fill_quantity",
        ):
            value = cls._read(response, field_name, None)
            if value not in (None, 0, 0.0, [], {}):
                return True
        return cls._broker_status(response) in {
            "PARTIALLY_FILLED",
            "PARTIAL_FILL",
            "FILLED",
            "COMPLETED",
        }

    def _persist(self, order: Order) -> None:
        self.repository.add(order)
        if OrderStatus.parse(order.status).terminal:
            self.queue.remove(order.id)

    def dispatch(
        self,
        order: Order,
        *,
        connector: Any = None,
        raise_on_error: bool = False,
    ) -> OrderResponse:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        self.validator.validate_or_raise(order)
        current = OrderStatus.parse(order.status)
        if current is not OrderStatus.SUBMITTED:
            raise ValueError(
                "A ordem deve estar SUBMITTED antes do despacho; "
                f"estado atual: {current.value}."
            )

        try:
            raw_response = self.router.route(order, connector=connector)
            response = OrderResponse(order, raw_response)
            broker_status = self._broker_status(raw_response)

            if response.success and response.accepted:
                if OrderStatus.parse(order.status) is OrderStatus.SUBMITTED:
                    self.lifecycle.accept(order)
                if response.external_id:
                    order.external_id = response.external_id
            elif broker_status in self.REJECTED_STATUSES:
                self.lifecycle.reject(order, reason=response.error or response.message)
            elif broker_status in self.CANCELLED_STATUSES:
                self.lifecycle.cancel(order, reason=response.error or response.message)
            else:
                self.lifecycle.fail(
                    order,
                    reason=response.error or response.message or "BROKER_DISPATCH_FAILED",
                )

            fill_pending = self._has_fill(raw_response)
            if fill_pending:
                order.metadata["broker_fill_pending"] = True
                response.metadata["fill_requires_order_executor"] = True

            self._persist(order)
            response.status = OrderStatus.parse(order.status).value
            self.last_report = {
                "order_id": order.id,
                "platform": order.platform,
                "status": order.status.value,
                "success": response.success,
                "accepted": response.accepted,
                "fill_pending": fill_pending,
                "error": response.error,
            }
            return response

        except Exception as exc:
            current = OrderStatus.parse(order.status)
            if not current.terminal:
                try:
                    self.lifecycle.fail(order, reason=str(exc))
                except Exception:
                    pass
            self._persist(order)
            failure = OrderResponse.failure(order, exc)
            failure.status = OrderStatus.parse(order.status).value
            self.last_report = {
                "order_id": order.id,
                "platform": order.platform,
                "status": order.status.value,
                "success": False,
                "accepted": False,
                "fill_pending": False,
                "error": str(exc),
            }
            if raise_on_error:
                raise
            return failure


order_dispatcher = OrderDispatcher()
