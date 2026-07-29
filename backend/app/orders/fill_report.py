from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any

from app.orders.fill import Fill
from app.orders.order_execution_report import OrderExecutionReport
from app.orders.order_status import OrderStatus


class FillReport:
    """Relatório normalizado produzido pelo processamento oficial de um fill.

    Mantém compatibilidade com ``FillReport(order, quantity, price)`` e pode
    ser construído a partir de ``OrderExecutionReport``.
    """

    def __init__(
        self,
        order: Any,
        quantity: Any = 0.0,
        price: Any = 0.0,
        fee: Any = 0.0,
        *,
        fill: Fill | Mapping[str, Any] | None = None,
        execution_report: OrderExecutionReport | Mapping[str, Any] | None = None,
        success: bool | None = None,
        message: str = "",
        error: str | None = None,
        cumulative: bool = False,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")

        self.order_id = str(getattr(order, "id", "") or "").strip()
        if not self.order_id:
            raise ValueError("A ordem deve possuir um ID válido.")

        self.platform = str(getattr(order, "platform", "") or "")
        self.symbol = str(getattr(order, "symbol", "") or "")
        self.status = OrderStatus.parse(getattr(order, "status", OrderStatus.CREATED)).value
        self.filled_quantity = float(getattr(order, "filled_quantity", 0.0) or 0.0)
        remaining = getattr(order, "remaining_quantity", 0.0)
        self.remaining_quantity = float(remaining() if callable(remaining) else remaining or 0.0)
        self.average_price = float(getattr(order, "average_price", 0.0) or 0.0)
        self.fees_paid = float(getattr(order, "fees_paid", 0.0) or 0.0)
        self.external_id = str(getattr(order, "external_id", "") or "")

        report_data = (
            execution_report.to_dict()
            if hasattr(execution_report, "to_dict")
            else dict(execution_report or {})
        )

        raw_fill = fill
        if raw_fill is None and report_data:
            raw_fill = report_data.get("fill")

        if isinstance(raw_fill, Fill):
            resolved_fill = raw_fill
        elif isinstance(raw_fill, Mapping) and float(raw_fill.get("quantity", 0.0) or 0.0) > 0:
            resolved_fill = Fill(
                order_id=self.order_id,
                quantity=raw_fill.get("quantity"),
                price=raw_fill.get("price"),
                fee=raw_fill.get("fee", fee),
                exchange=self.platform,
                external_id=raw_fill.get("external_id", self.external_id),
                cumulative=raw_fill.get("cumulative", cumulative),
                timestamp=raw_fill.get("timestamp"),
                metadata={"source": "order_execution_report"},
            )
        elif float(quantity or 0.0) > 0 and float(price or 0.0) > 0:
            resolved_fill = Fill(
                order_id=self.order_id,
                quantity=quantity,
                price=price,
                fee=fee,
                exchange=self.platform,
                external_id=self.external_id,
                cumulative=cumulative,
            )
        else:
            resolved_fill = None

        self.fill = resolved_fill
        self.quantity = resolved_fill.quantity if resolved_fill else float(
            report_data.get("applied_quantity", quantity or 0.0) or 0.0
        )
        self.applied_quantity = self.quantity
        self.price = resolved_fill.price if resolved_fill else float(price or 0.0)
        self.fee = resolved_fill.fee if resolved_fill else float(fee or 0.0)
        self.cumulative = resolved_fill.cumulative if resolved_fill else bool(cumulative)

        inferred_success = bool(
            report_data.get(
                "success",
                self.status in {OrderStatus.PARTIALLY_FILLED.value, OrderStatus.FILLED.value},
            )
        )
        self.success = inferred_success if success is None else bool(success)
        self.message = str(report_data.get("message", message) or "").strip()
        resolved_error = report_data.get("error", error)
        self.error = None if resolved_error in (None, "") else str(resolved_error)
        self.timestamp = datetime.now(timezone.utc)
        self.metadata = dict(metadata or {})
        if report_data:
            self.metadata.setdefault("execution_report", report_data)

    @property
    def fill_id(self) -> str | None:
        return self.fill.id if self.fill else None

    @property
    def value(self) -> float:
        return self.fill.value if self.fill else 0.0

    @classmethod
    def from_execution(
        cls,
        order: Any,
        execution_report: OrderExecutionReport | Mapping[str, Any],
        *,
        metadata: Mapping[str, Any] | None = None,
    ) -> "FillReport":
        return cls(
            order,
            execution_report=execution_report,
            metadata=metadata,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "platform": self.platform,
            "symbol": self.symbol,
            "status": self.status,
            "success": self.success,
            "quantity": self.quantity,
            "applied_quantity": self.applied_quantity,
            "price": self.price,
            "fee": self.fee,
            "value": self.value,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "fees_paid": self.fees_paid,
            "external_id": self.external_id,
            "cumulative": self.cumulative,
            "fill_id": self.fill_id,
            "fill": self.fill.to_dict() if self.fill else None,
            "message": self.message,
            "error": self.error,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }
