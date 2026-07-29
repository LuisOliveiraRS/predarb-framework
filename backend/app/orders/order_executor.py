from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.orders.order import Order
from app.orders.order_execution_report import OrderExecutionReport
from app.orders.order_lifecycle import OrderLifecycle, order_lifecycle
from app.orders.order_queue import OrderQueue, order_queue
from app.orders.order_repository import OrderRepository, order_repository
from app.orders.order_status import OrderStatus


class OrderExecutor:
    """Processa confirmações e fills recebidos das exchanges.

    Toda alteração de status passa pelo ``OrderLifecycle``. O executor aceita
    a assinatura legada ``execute(order, quantity, price, fee=0)`` e também
    respostas estruturadas de conectores.
    """

    ACCEPTED_STATUSES = {"ACCEPTED", "ACKNOWLEDGED", "OPEN", "SUBMITTED"}
    PARTIAL_STATUSES = {"PARTIALLY_FILLED", "PARTIAL_FILL", "PARTIAL"}
    FILLED_STATUSES = {"FILLED", "COMPLETED"}
    REJECTED_STATUSES = {"REJECTED", "DECLINED"}
    CANCELLED_STATUSES = {"CANCELLED", "CANCELED"}
    EXPIRED_STATUSES = {"EXPIRED"}
    FAILED_STATUSES = {"FAILED", "ERROR"}

    def __init__(
        self,
        *,
        lifecycle: OrderLifecycle | None = None,
        repository: OrderRepository | None = None,
        queue: OrderQueue | None = None,
    ) -> None:
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

    @staticmethod
    def _number(value: Any, field_name: str, *, default: float | None = None) -> float | None:
        if value is None:
            return default
        if isinstance(value, bool):
            raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
        try:
            return float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc

    @classmethod
    def _status(cls, response: Any, explicit: Any = None) -> str:
        value = explicit
        if value is None:
            value = cls._read(response, "status", cls._read(response, "state", ""))
        value = getattr(value, "value", value)
        return str(value or "").strip().upper()

    def _resolve_order(self, order_or_id: Any) -> Order:
        if isinstance(order_or_id, Order):
            return order_or_id
        return self.repository.require(order_or_id)

    @classmethod
    def _extract_fill(
        cls,
        response: Any,
        *,
        quantity: Any,
        price: Any,
        fee: Any,
        cumulative: bool | None,
        current_filled: float,
    ) -> tuple[float | None, float | None, float, bool]:
        fill = cls._read(response, "fill", None)
        source = fill if fill is not None else response

        incremental_quantity = quantity
        if incremental_quantity is None:
            incremental_quantity = cls._read(
                source,
                "last_fill_quantity",
                cls._read(
                    source,
                    "executed_quantity",
                    cls._read(source, "quantity", None),
                ),
            )

        cumulative_quantity = cls._read(
            source,
            "cumulative_filled_quantity",
            cls._read(source, "filled_quantity", None),
        )

        resolved_cumulative = bool(cumulative) if cumulative is not None else (
            incremental_quantity is None and cumulative_quantity is not None
        )

        if resolved_cumulative and cumulative_quantity is not None:
            cumulative_value = cls._number(
                cumulative_quantity,
                "filled_quantity",
            )
            applied_quantity = max(0.0, float(cumulative_value or 0.0) - current_filled)
        else:
            applied_quantity = cls._number(
                incremental_quantity,
                "quantity",
                default=None,
            )

        fill_price = price
        if fill_price is None:
            fill_price = cls._read(
                source,
                "fill_price",
                cls._read(
                    source,
                    "average_price",
                    cls._read(source, "price", None),
                ),
            )
        resolved_price = cls._number(fill_price, "price", default=None)

        resolved_fee = fee
        if resolved_fee in (None, 0, 0.0):
            resolved_fee = cls._read(source, "fee", cls._read(source, "fees", 0.0))
        fee_value = cls._number(resolved_fee, "fee", default=0.0) or 0.0

        return applied_quantity, resolved_price, fee_value, resolved_cumulative

    def _persist(self, order: Order) -> None:
        self.repository.add(order)
        if OrderStatus.parse(order.status).terminal:
            self.queue.remove(order.id)

    def execute(
        self,
        order: Order | str,
        quantity: Any = None,
        price: Any = None,
        fee: Any = 0.0,
        *,
        status: Any = None,
        response: Any = None,
        cumulative: bool | None = None,
        reason: str = "",
        external_id: str | None = None,
    ) -> OrderExecutionReport:
        resolved_order = self._resolve_order(order)
        broker_status = self._status(response, status)
        current = OrderStatus.parse(resolved_order.status)

        if external_id is None:
            external_id = self._read(
                response,
                "external_id",
                self._read(response, "order_id", self._read(response, "id", None)),
            )
        if external_id:
            resolved_order.external_id = str(external_id)

        applied_quantity, fill_price, fee_value, resolved_cumulative = self._extract_fill(
            response,
            quantity=quantity,
            price=price,
            fee=fee,
            cumulative=cumulative,
            current_filled=float(resolved_order.filled_quantity),
        )

        fill_data: dict[str, Any] | None = None
        error: str | None = None
        message = ""

        try:
            if broker_status in self.REJECTED_STATUSES:
                self.lifecycle.reject(resolved_order, reason=reason or "BROKER_REJECTED")
            elif broker_status in self.CANCELLED_STATUSES:
                self.lifecycle.cancel(resolved_order, reason=reason or "BROKER_CANCELLED")
            elif broker_status in self.EXPIRED_STATUSES:
                self.lifecycle.expire(resolved_order, reason=reason or "BROKER_EXPIRED")
            elif broker_status in self.FAILED_STATUSES:
                self.lifecycle.fail(resolved_order, reason=reason or "BROKER_FAILED")
            else:
                has_fill = applied_quantity is not None and applied_quantity > 0
                wants_fill = (
                    has_fill
                    or broker_status in self.PARTIAL_STATUSES
                    or broker_status in self.FILLED_STATUSES
                )

                if wants_fill:
                    if not has_fill:
                        if broker_status in self.FILLED_STATUSES:
                            applied_quantity = resolved_order.remaining_quantity
                        else:
                            raise ValueError(
                                "Confirmação de fill parcial sem quantidade executada."
                            )
                    if fill_price is None or fill_price <= 0:
                        raise ValueError("Confirmação de fill sem preço válido.")
                    if current is OrderStatus.SUBMITTED:
                        self.lifecycle.accept(resolved_order)
                    self.lifecycle.apply_fill(
                        resolved_order,
                        applied_quantity,
                        fill_price,
                        fee=fee_value,
                    )
                    fill_data = {
                        "quantity": round(float(applied_quantity), 8),
                        "price": float(fill_price),
                        "fee": float(fee_value),
                        "cumulative": resolved_cumulative,
                        "external_id": resolved_order.external_id,
                        "timestamp": (
                            resolved_order.last_fill_time.isoformat()
                            if resolved_order.last_fill_time is not None
                            else None
                        ),
                    }
                elif broker_status in self.ACCEPTED_STATUSES or not broker_status:
                    if current is OrderStatus.SUBMITTED:
                        self.lifecycle.accept(resolved_order)
                    elif current not in {
                        OrderStatus.ACCEPTED,
                        OrderStatus.PARTIALLY_FILLED,
                        OrderStatus.FILLED,
                    }:
                        raise ValueError(
                            "Uma confirmação de aceitação exige ordem SUBMITTED."
                        )
                else:
                    raise ValueError(f"Status de execução desconhecido: {broker_status!r}.")

            resolved_order.metadata.pop("broker_fill_pending", None)
            self._persist(resolved_order)

        except Exception as exc:
            error = str(exc)
            message = "Falha ao processar confirmação da exchange."
            current_after_error = OrderStatus.parse(resolved_order.status)
            if not current_after_error.terminal:
                try:
                    self.lifecycle.fail(resolved_order, reason=error)
                except Exception:
                    pass
            self._persist(resolved_order)

        final_status = OrderStatus.parse(resolved_order.status)
        successful_status = final_status in {
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
        }
        if error is None and not successful_status:
            message = message or reason or broker_status or final_status.value

        report = OrderExecutionReport(
            resolved_order,
            fill_data,
            applied_quantity=(fill_data or {}).get("quantity", 0.0),
            response=response,
            success=error is None and successful_status,
            message=message,
            error=error,
            metadata={
                "broker_status": broker_status,
                "cumulative": resolved_cumulative,
            },
        )
        self.last_report = report.to_dict()
        return report

    process_execution = execute


order_executor = OrderExecutor()
