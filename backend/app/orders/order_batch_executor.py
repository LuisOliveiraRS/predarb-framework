from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Any, Callable

from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.order_batch_report import OrderBatchReport
from app.orders.order_response import OrderResponse
from app.orders.order_sender import OrderSender, order_sender
from app.orders.order_status import OrderStatus


class OrderBatchExecutor:
    """Despacha um lote de ordens com proteção explícita de execução real.

    Em falha parcial, o executor não altera localmente uma ordem aceita para
    ``CANCELLED`` sem confirmação externa. Quando nenhum cancelador é
    injetado, o relatório marca ``compensation_required=True``.
    """

    def __init__(
        self,
        *,
        sender: OrderSender | None = None,
        enabled: bool = False,
        canceller: Any = None,
        max_workers: int = 8,
    ) -> None:
        self.sender = sender if sender is not None else order_sender
        self.enabled = bool(enabled)
        self.canceller = canceller
        self.max_workers = max(1, int(max_workers))
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_batch(value: Any) -> OrderBatch:
        if isinstance(value, OrderBatch):
            return value
        if isinstance(value, Order):
            return OrderBatch([value])
        return OrderBatch(value)

    @staticmethod
    def _require_submitted(order: Order) -> None:
        status = OrderStatus.parse(order.status)
        if status is not OrderStatus.SUBMITTED:
            raise ValueError(
                "A ordem deve estar SUBMITTED antes da execução em lote; "
                f"estado atual: {status.value}."
            )

    def _send_one(self, order: Order) -> OrderResponse:
        try:
            self._require_submitted(order)
            return self.sender.send(order)
        except Exception as exc:
            return OrderResponse.failure(order, exc)

    @staticmethod
    def _resolve_canceller(canceller: Any) -> Callable[..., Any] | None:
        if canceller is None:
            return None
        if callable(canceller):
            return canceller
        method = getattr(canceller, "cancel", None)
        return method if callable(method) else None

    @staticmethod
    def _invoke_cancel(
        callable_canceller: Callable[..., Any],
        order: Order,
        reason: str,
    ) -> Any:
        try:
            return callable_canceller(order, reason=reason)
        except TypeError:
            try:
                return callable_canceller(order, reason)
            except TypeError:
                return callable_canceller(order)

    def _compensate(
        self,
        orders: list[Order],
        responses: list[OrderResponse],
        *,
        canceller: Any,
    ) -> dict[str, Any]:
        successful_orders = [
            order
            for order, response in zip(orders, responses)
            if response.success and response.accepted
        ]

        failed_count = sum(1 for response in responses if not response.success)
        required = bool(successful_orders and failed_count)
        result: dict[str, Any] = {
            "required": required,
            "attempted": False,
            "succeeded": False,
            "orders": [],
            "errors": [],
        }

        if not required:
            return result

        callable_canceller = self._resolve_canceller(canceller)
        if callable_canceller is None:
            for order in successful_orders:
                order.metadata["compensation_required"] = True
                result["orders"].append(
                    {
                        "order_id": order.id,
                        "platform": order.platform,
                        "status": "REQUIRED",
                    }
                )
            return result

        result["attempted"] = True
        all_succeeded = True
        for order in successful_orders:
            try:
                response = self._invoke_cancel(
                    callable_canceller,
                    order,
                    "BATCH_PARTIAL_FAILURE",
                )
                succeeded = response is not False and response is not None
                all_succeeded = all_succeeded and succeeded
                result["orders"].append(
                    {
                        "order_id": order.id,
                        "platform": order.platform,
                        "status": "CANCELLED" if succeeded else "FAILED",
                        "response": response,
                    }
                )
                if not succeeded:
                    result["errors"].append(
                        f"Cancelamento não confirmado para {order.id}."
                    )
            except Exception as exc:
                all_succeeded = False
                result["errors"].append(str(exc))
                result["orders"].append(
                    {
                        "order_id": order.id,
                        "platform": order.platform,
                        "status": "FAILED",
                        "error": str(exc),
                    }
                )

        result["succeeded"] = all_succeeded
        return result

    def _dispatch_sequential(self, orders: list[Order]) -> list[OrderResponse]:
        return [self._send_one(order) for order in orders]

    def _dispatch_parallel(self, orders: list[Order]) -> list[OrderResponse]:
        responses: list[OrderResponse | None] = [None] * len(orders)
        workers = min(self.max_workers, len(orders))
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {
                executor.submit(self._send_one, order): index
                for index, order in enumerate(orders)
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    responses[index] = future.result()
                except Exception as exc:
                    responses[index] = OrderResponse.failure(orders[index], exc)

        return [
            response
            if response is not None
            else OrderResponse.failure(orders[index], "BATCH_RESPONSE_MISSING")
            for index, response in enumerate(responses)
        ]

    def execute(
        self,
        batch: Any,
        *,
        enabled: bool | None = None,
        simultaneous: bool | None = None,
        cancel_on_failure: bool | None = None,
        canceller: Any = None,
    ) -> OrderBatchReport:
        resolved_batch = self._as_batch(batch)
        resolved_batch.validate_or_raise()
        orders = resolved_batch.all()

        resolved_enabled = self.enabled if enabled is None else bool(enabled)
        resolved_simultaneous = (
            resolved_batch.simultaneous
            if simultaneous is None
            else bool(simultaneous)
        )
        resolved_cancel = (
            resolved_batch.cancel_on_failure
            if cancel_on_failure is None
            else bool(cancel_on_failure)
        )

        if not resolved_enabled:
            responses = [OrderResponse.disabled(order) for order in orders]
            for response in responses:
                response.status = "DISABLED"
            report = OrderBatchReport(
                responses,
                batch=resolved_batch,
                metadata={
                    "enabled": False,
                    "simultaneous": resolved_simultaneous,
                },
            )
            self.last_report = report.to_dict()
            return report

        responses = (
            self._dispatch_parallel(orders)
            if resolved_simultaneous and len(orders) > 1
            else self._dispatch_sequential(orders)
        )

        compensation: dict[str, Any] = {}
        if resolved_cancel:
            compensation = self._compensate(
                orders,
                responses,
                canceller=self.canceller if canceller is None else canceller,
            )

        report = OrderBatchReport(
            responses,
            batch=resolved_batch,
            compensation=compensation,
            metadata={
                "enabled": True,
                "simultaneous": resolved_simultaneous,
                "cancel_on_failure": resolved_cancel,
            },
        )
        self.last_report = report.to_dict()
        return report

    execute_pair = execute

    def execute_responses(self, batch: Any, **kwargs: Any) -> list[OrderResponse]:
        """Interface legada que retorna somente a lista de respostas."""

        return self.execute(batch, **kwargs).to_list()


order_batch_executor = OrderBatchExecutor()
