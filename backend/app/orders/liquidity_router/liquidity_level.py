from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.orders.order_side import OrderSide


def _number(value: Any, field_name: str, *, minimum: float = 0.0) -> float:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} não pode ser booleano.")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} deve ser numérico.") from exc
    if not isfinite(number):
        raise ValueError(f"{field_name} deve ser finito.")
    if number < minimum:
        raise ValueError(f"{field_name} deve ser maior ou igual a {minimum}.")
    return number


@dataclass(slots=True)
class LiquidityLevel:
    exchange: str
    bid: float
    ask: float
    quantity: float
    spread: float | None = None
    connector: Any = None
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def __post_init__(self) -> None:
        self.exchange = str(self.exchange or "").strip()
        if not self.exchange:
            raise ValueError("exchange é obrigatório para LiquidityLevel.")
        self.bid = _number(self.bid, "bid")
        self.ask = _number(self.ask, "ask")
        self.quantity = _number(self.quantity, "quantity")
        calculated_spread = max(0.0, self.ask - self.bid)
        self.spread = _number(
            calculated_spread if self.spread is None else self.spread,
            "spread",
        )
        self.enabled = bool(self.enabled)
        self.metadata = dict(self.metadata or {})
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

    @property
    def available(self) -> bool:
        return self.enabled and self.quantity > 0

    @property
    def connector_name(self) -> str:
        if isinstance(self.connector, str):
            return self.connector.strip()
        return str(getattr(self.connector, "name", self.exchange) or self.exchange).strip()

    def price_for(self, side: OrderSide | str) -> float:
        resolved = OrderSide.parse(side)
        return self.ask if resolved is OrderSide.BUY else self.bid

    @classmethod
    def from_value(cls, value: Any) -> "LiquidityLevel":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                exchange=value.get("exchange", value.get("name", value.get("platform", ""))),
                bid=value.get("bid", value.get("price", 0.0)),
                ask=value.get("ask", value.get("price", 0.0)),
                quantity=value.get("quantity", value.get("liquidity", value.get("available_quantity", 0.0))),
                spread=value.get("spread"),
                connector=value.get("connector"),
                enabled=value.get("enabled", True),
                metadata=value.get("metadata", {}),
            )
        return cls(
            exchange=getattr(value, "exchange", getattr(value, "name", "")),
            bid=getattr(value, "bid", getattr(value, "price", 0.0)),
            ask=getattr(value, "ask", getattr(value, "price", 0.0)),
            quantity=getattr(value, "quantity", getattr(value, "liquidity", 0.0)),
            spread=getattr(value, "spread", None),
            connector=getattr(value, "connector", None),
            enabled=getattr(value, "enabled", True),
            metadata=getattr(value, "metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange,
            "bid": self.bid,
            "ask": self.ask,
            "quantity": self.quantity,
            "spread": self.spread,
            "connector": self.connector_name,
            "enabled": self.enabled,
            "available": self.available,
            "metadata": dict(self.metadata),
            "timestamp": self.timestamp.isoformat(),
        }
