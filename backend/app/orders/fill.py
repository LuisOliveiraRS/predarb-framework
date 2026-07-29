from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4


def _number(
    value: Any,
    field_name: str,
    *,
    positive: bool = False,
) -> float:
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


def _datetime(value: Any) -> datetime:
    if value is None:
        return datetime.now(timezone.utc)

    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str):
        normalized = value.strip()
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        parsed = datetime.fromisoformat(normalized)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)

    raise TypeError("timestamp deve ser datetime ou string ISO-8601.")


@dataclass(slots=True)
class Fill:
    """Registro imutável de uma quantidade efetivamente aplicada a uma ordem."""

    order_id: str
    quantity: float
    price: float
    fee: float = 0.0
    exchange: str | None = None
    id: str = field(default_factory=lambda: str(uuid4()))
    external_id: str = ""
    cumulative: bool = False
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.order_id = str(self.order_id or "").strip()
        if not self.order_id:
            raise ValueError("order_id não pode ser vazio.")

        self.id = str(self.id or uuid4()).strip()
        self.quantity = round(_number(self.quantity, "quantity", positive=True), 8)
        self.price = _number(self.price, "price", positive=True)
        self.fee = round(_number(self.fee, "fee"), 8)
        self.exchange = str(self.exchange or "").strip() or None
        self.external_id = str(self.external_id or "").strip()
        self.cumulative = bool(self.cumulative)
        self.timestamp = _datetime(self.timestamp)
        self.metadata = dict(self.metadata or {})

    @property
    def value(self) -> float:
        return round(self.quantity * self.price, 8)

    @property
    def gross_value(self) -> float:
        return self.value

    @property
    def total_cost(self) -> float:
        return round(self.value + self.fee, 8)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "order_id": self.order_id,
            "quantity": self.quantity,
            "price": self.price,
            "value": self.value,
            "gross_value": self.gross_value,
            "fee": self.fee,
            "total_cost": self.total_cost,
            "exchange": self.exchange,
            "external_id": self.external_id,
            "cumulative": self.cumulative,
            "timestamp": self.timestamp.isoformat(),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Fill":
        if not isinstance(data, Mapping):
            raise TypeError("Fill.from_dict exige um Mapping.")

        return cls(
            order_id=data.get("order_id", ""),
            quantity=data.get("quantity", 0.0),
            price=data.get("price", 0.0),
            fee=data.get("fee", 0.0),
            exchange=data.get("exchange"),
            id=data.get("id") or str(uuid4()),
            external_id=data.get("external_id", ""),
            cumulative=data.get("cumulative", False),
            timestamp=data.get("timestamp"),
            metadata=dict(data.get("metadata", {}) or {}),
        )
