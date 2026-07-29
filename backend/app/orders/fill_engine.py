from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.orders.fill_report import FillReport
from app.orders.order import Order
from app.orders.order_executor import OrderExecutor, order_executor
from app.orders.order_status import OrderStatus


class FillEngine:
    """Fachada de compatibilidade para o ``OrderExecutor`` oficial.

    O engine não altera quantidades nem status diretamente. Todo fill passa
    por ``OrderExecutor -> OrderLifecycle -> OrderStateMachine``.
    """

    def __init__(self, *, executor: OrderExecutor | None = None) -> None:
        self.executor = executor if executor is not None else order_executor
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @staticmethod
    def _number(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc
        if number <= 0:
            raise ValueError(f"O campo {field_name!r} deve ser maior que zero.")
        return number

    def _resolve_order(self, order_or_id: Order | str) -> Order:
        if isinstance(order_or_id, Order):
            return order_or_id
        return self.executor.repository.require(order_or_id)

    @classmethod
    def _cumulative_quantity(cls, response: Any) -> float | None:
        value = cls._read(
            response,
            "cumulative_filled_quantity",
            cls._read(response, "filled_quantity", None),
        )
        if value is None:
            return None
        try:
            return float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _noop_report(order: Order, *, cumulative: bool, message: str) -> FillReport:
        return FillReport(
            order,
            success=True,
            cumulative=cumulative,
            message=message,
            metadata={"idempotent": True},
        )

    def process_fill(
        self,
        order: Order | str,
        quantity: Any = None,
        price: Any = None,
        fee: Any = 0.0,
        *,
        response: Any = None,
        cumulative: bool | None = None,
        status: Any = None,
        reason: str = "",
        external_id: str | None = None,
    ) -> FillReport:
        resolved_order = self._resolve_order(order)
        current = OrderStatus.parse(resolved_order.status)

        if current not in {
            OrderStatus.SUBMITTED,
            OrderStatus.ACCEPTED,
            OrderStatus.PARTIALLY_FILLED,
            OrderStatus.FILLED,
        }:
            raise ValueError(
                "Um fill somente pode ser processado para uma ordem "
                "SUBMITTED, ACCEPTED ou PARTIALLY_FILLED."
            )

        response_cumulative = self._cumulative_quantity(response)
        resolved_cumulative = bool(cumulative) if cumulative is not None else (
            response_cumulative is not None and quantity is None
        )

        target_cumulative = response_cumulative
        if resolved_cumulative and target_cumulative is None and quantity is not None:
            target_cumulative = float(quantity)

        if (
            resolved_cumulative
            and target_cumulative is not None
            and target_cumulative <= float(resolved_order.filled_quantity)
        ):
            report = self._noop_report(
                resolved_order,
                cumulative=True,
                message="DUPLICATE_CUMULATIVE_FILL_IGNORED",
            )
            self.last_report = report.to_dict()
            return report

        if current is OrderStatus.FILLED:
            report = self._noop_report(
                resolved_order,
                cumulative=resolved_cumulative,
                message="ORDER_ALREADY_FILLED",
            )
            self.last_report = report.to_dict()
            return report

        payload = response
        execute_quantity = quantity
        execute_price = price

        if response is None and resolved_cumulative:
            if target_cumulative is None:
                raise ValueError("Fill cumulativo exige filled_quantity.")
            payload = {
                "status": (
                    "FILLED"
                    if target_cumulative >= float(resolved_order.quantity)
                    else "PARTIALLY_FILLED"
                ),
                "filled_quantity": target_cumulative,
                "average_price": price,
                "fee": fee,
            }
            execute_quantity = None
            execute_price = None

        if response is None and not resolved_cumulative:
            resolved_quantity = self._number(quantity, "quantity")
            resolved_price = self._number(price, "price")
            inferred_status = (
                "FILLED"
                if resolved_quantity >= float(resolved_order.remaining_quantity)
                else "PARTIALLY_FILLED"
            )
            status = status or inferred_status
            execute_quantity = resolved_quantity
            execute_price = resolved_price

        execution_report = self.executor.execute(
            resolved_order,
            execute_quantity,
            execute_price,
            fee,
            status=status,
            response=payload,
            cumulative=resolved_cumulative,
            reason=reason,
            external_id=external_id,
        )

        report = FillReport.from_execution(
            resolved_order,
            execution_report,
            metadata={"source": "fill_engine"},
        )
        self.last_report = report.to_dict()
        return report

    process = process_fill

    def execute_fill(
        self,
        order: Order | str,
        quantity: Any,
        price: Any,
        fee: Any = 0.0,
        **kwargs: Any,
    ) -> Order:
        """Assinatura legada: processa o fill e retorna a ordem atualizada."""
        resolved_order = self._resolve_order(order)
        self.process_fill(
            resolved_order,
            quantity,
            price,
            fee,
            **kwargs,
        )
        return resolved_order

    execute = process_fill


fill_engine = FillEngine()
