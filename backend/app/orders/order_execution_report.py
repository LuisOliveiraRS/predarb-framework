from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any

from app.orders.order_status import OrderStatus


def _read(target: Any, field_name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(field_name, default)
    if target is None:
        return default
    return getattr(target, field_name, default)


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.isoformat()
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return _serialize(to_dict())
    return {
        key: _serialize(item)
        for key, item in vars(value).items()
    } if hasattr(value, "__dict__") else value


@dataclass(init=False, slots=True)
class OrderExecutionReport:
    """Relatório normalizado produzido após uma confirmação da exchange."""

    order_id: str
    platform: str
    status: str
    success: bool
    quantity: float
    filled_quantity: float
    applied_quantity: float
    remaining: float
    average_price: float
    fees_paid: float
    fill: Any
    response: Any
    message: str
    error: str | None
    created_at: datetime
    metadata: dict[str, Any]

    def __init__(
        self,
        order: Any,
        fill: Any = None,
        *,
        applied_quantity: float | None = None,
        response: Any = None,
        success: bool | None = None,
        message: str = "",
        error: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        if order is None:
            raise ValueError("order não pode ser None.")

        status = OrderStatus.parse(getattr(order, "status", OrderStatus.CREATED))
        inferred_applied = _read(fill, "quantity", 0.0)
        self.order_id = str(getattr(order, "id", "") or "")
        self.platform = str(getattr(order, "platform", "") or "")
        self.status = status.value
        self.success = bool(
            (status in {OrderStatus.ACCEPTED, OrderStatus.PARTIALLY_FILLED, OrderStatus.FILLED})
            if success is None
            else success
        )
        self.quantity = float(getattr(order, "quantity", 0.0) or 0.0)
        self.filled_quantity = float(
            getattr(order, "filled_quantity", 0.0) or 0.0
        )
        self.applied_quantity = float(
            inferred_applied if applied_quantity is None else applied_quantity
        )
        remaining = getattr(order, "remaining_quantity", 0.0)
        self.remaining = float(remaining() if callable(remaining) else remaining or 0.0)
        self.average_price = float(getattr(order, "average_price", 0.0) or 0.0)
        self.fees_paid = float(getattr(order, "fees_paid", 0.0) or 0.0)
        self.fill = fill
        self.response = response
        self.message = str(message or "").strip()
        self.error = None if error is None else str(error)
        self.created_at = datetime.now(timezone.utc)
        self.metadata = dict(metadata or {})

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "platform": self.platform,
            "status": self.status,
            "success": self.success,
            "quantity": self.quantity,
            "filled_quantity": self.filled_quantity,
            "applied_quantity": self.applied_quantity,
            "remaining": self.remaining,
            "average_price": self.average_price,
            "fees_paid": self.fees_paid,
            "fill": _serialize(self.fill),
            "response": _serialize(self.response),
            "message": self.message,
            "error": self.error,
            "metadata": _serialize(self.metadata),
            "created_at": self.created_at.isoformat(),
        }
