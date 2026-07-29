from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4

from app.orders.execution_policy import ExecutionPolicy
from app.orders.order_side import OrderSide
from app.orders.order_status import OrderStatus
from app.orders.order_type import OrderType
from app.orders.time_in_force import TimeInForce


def _number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise TypeError(f"O campo {field_name!r} não pode ser booleano.")

    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc

    if not isfinite(number):
        raise ValueError(f"O campo {field_name!r} deve ser finito.")

    if minimum is not None and number < minimum:
        raise ValueError(
            f"O campo {field_name!r} deve ser maior ou igual a {minimum}."
        )

    return number


def _datetime(value: Any, field_name: str) -> datetime | None:
    if value is None:
        return None

    if isinstance(value, datetime):
        return value if value.tzinfo is not None else value.replace(tzinfo=timezone.utc)

    if isinstance(value, str):
        normalized = value.strip()
        if not normalized:
            return None
        if normalized.endswith("Z"):
            normalized = normalized[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError as exc:
            raise ValueError(f"O campo {field_name!r} deve usar ISO-8601.") from exc
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=timezone.utc)

    raise TypeError(f"O campo {field_name!r} deve ser datetime ou string ISO-8601.")


@dataclass(init=False, slots=True)
class Order:
    """
    Modelo oficial de ordem do OMS.

    Preserva o construtor legado:

        Order(symbol, side, quantity, order_type, price)

    e aceita o formato institucional:

        Order(platform=..., market=..., side=..., quantity=...)
    """

    id: str
    platform: str
    market: str
    symbol: str
    side: OrderSide
    quantity: float
    price: float
    order_type: OrderType
    status: OrderStatus
    time_in_force: TimeInForce

    created_at: datetime
    updated_at: datetime
    submitted_at: datetime | None
    accepted_at: datetime | None
    executed_at: datetime | None
    cancelled_at: datetime | None

    filled_quantity: float
    average_price: float
    last_fill_price: float
    last_fill_quantity: float
    last_fill_time: datetime | None
    fees_paid: float

    retry_count: int
    reject_reason: str
    cancel_reason: str
    external_id: str
    client_order_id: str

    opportunity_id: str
    leg: str
    mode: str

    execution_policy: ExecutionPolicy
    execution_targets: list[Any]
    twap_interval: float
    twap_slices: int
    visible_quantity: float
    split_parts: int

    metadata: dict[str, Any]

    def __init__(
        self,
        symbol: str | None = None,
        side: OrderSide | str | None = None,
        quantity: Any = None,
        order_type: OrderType | str = OrderType.MARKET,
        price: Any = 0.0,
        *,
        platform: str | None = None,
        market: str | None = None,
        time_in_force: TimeInForce | str = TimeInForce.GTC,
        status: OrderStatus | str = OrderStatus.CREATED,
        order_id: str | None = None,
        id: str | None = None,
        created_at: datetime | str | None = None,
        updated_at: datetime | str | None = None,
        submitted_at: datetime | str | None = None,
        accepted_at: datetime | str | None = None,
        executed_at: datetime | str | None = None,
        cancelled_at: datetime | str | None = None,
        filled_quantity: Any = 0.0,
        average_price: Any = 0.0,
        last_fill_price: Any = 0.0,
        last_fill_quantity: Any = 0.0,
        last_fill_time: datetime | str | None = None,
        fees_paid: Any = 0.0,
        retry_count: int = 0,
        reject_reason: str = "",
        cancel_reason: str = "",
        external_id: str = "",
        client_order_id: str = "",
        opportunity_id: str = "",
        leg: str = "",
        mode: str = "OMS",
        execution_policy: ExecutionPolicy | str | None = None,
        execution_targets: list[Any] | None = None,
        twap_interval: Any = 30.0,
        twap_slices: int = 10,
        visible_quantity: Any | None = None,
        split_parts: int = 5,
        metadata: Mapping[str, Any] | None = None,
    ) -> None:
        resolved_symbol = str(symbol or market or "").strip()
        resolved_market = str(market or symbol or "").strip()

        self.id = str(order_id or id or uuid4()).strip()
        self.platform = str(platform or "").strip()
        self.market = resolved_market
        self.symbol = resolved_symbol
        self.side = OrderSide.parse(side)
        self.quantity = _number(quantity, "quantity", minimum=0.0)
        self.price = _number(price, "price", minimum=0.0)
        self.order_type = OrderType.parse(order_type)
        self.status = OrderStatus.parse(status)
        self.time_in_force = TimeInForce.parse(time_in_force)

        if self.quantity <= 0:
            raise ValueError("O campo 'quantity' deve ser maior que zero.")

        now = datetime.now(timezone.utc)
        self.created_at = _datetime(created_at, "created_at") or now
        self.updated_at = _datetime(updated_at, "updated_at") or self.created_at
        self.submitted_at = _datetime(submitted_at, "submitted_at")
        self.accepted_at = _datetime(accepted_at, "accepted_at")
        self.executed_at = _datetime(executed_at, "executed_at")
        self.cancelled_at = _datetime(cancelled_at, "cancelled_at")

        self.filled_quantity = _number(
            filled_quantity,
            "filled_quantity",
            minimum=0.0,
        )
        self.average_price = _number(average_price, "average_price", minimum=0.0)
        self.last_fill_price = _number(
            last_fill_price,
            "last_fill_price",
            minimum=0.0,
        )
        self.last_fill_quantity = _number(
            last_fill_quantity,
            "last_fill_quantity",
            minimum=0.0,
        )
        self.last_fill_time = _datetime(last_fill_time, "last_fill_time")
        self.fees_paid = _number(fees_paid, "fees_paid", minimum=0.0)

        if self.filled_quantity > self.quantity:
            raise ValueError("filled_quantity não pode exceder quantity.")

        if isinstance(retry_count, bool):
            raise TypeError("retry_count não pode ser booleano.")
        self.retry_count = int(retry_count)
        if self.retry_count < 0:
            raise ValueError("retry_count não pode ser negativo.")

        self.reject_reason = str(reject_reason or "").strip()
        self.cancel_reason = str(cancel_reason or "").strip()
        self.external_id = str(external_id or "").strip()
        self.client_order_id = str(client_order_id or "").strip()
        self.opportunity_id = str(opportunity_id or "").strip()
        self.leg = str(leg or "").strip().upper()
        self.mode = str(mode or "OMS").strip().upper()

        if execution_policy is None:
            execution_policy = (
                ExecutionPolicy.LIMIT
                if self.order_type is OrderType.LIMIT
                else ExecutionPolicy.MARKET
            )
        self.execution_policy = self._parse_execution_policy(execution_policy)
        self.execution_targets = list(execution_targets or [])
        self.twap_interval = _number(twap_interval, "twap_interval", minimum=0.0)

        if isinstance(twap_slices, bool) or isinstance(split_parts, bool):
            raise TypeError("twap_slices e split_parts devem ser inteiros.")
        self.twap_slices = int(twap_slices)
        self.split_parts = int(split_parts)
        if self.twap_slices <= 0 or self.split_parts <= 0:
            raise ValueError("twap_slices e split_parts devem ser maiores que zero.")

        default_visible = self.quantity * 0.10
        self.visible_quantity = _number(
            default_visible if visible_quantity is None else visible_quantity,
            "visible_quantity",
            minimum=0.0,
        )
        if self.visible_quantity > self.quantity:
            self.visible_quantity = self.quantity

        self.metadata = dict(metadata or {})

    @staticmethod
    def _parse_execution_policy(value: Any) -> ExecutionPolicy:
        if isinstance(value, ExecutionPolicy):
            return value
        if not isinstance(value, str):
            raise TypeError("execution_policy deve ser ExecutionPolicy ou string.")
        normalized = value.strip().upper()
        try:
            return ExecutionPolicy[normalized]
        except KeyError as exc:
            raise ValueError(f"Execution policy inválida: {value!r}.") from exc

    @property
    def remaining_quantity(self) -> float:
        return round(max(0.0, self.quantity - self.filled_quantity), 8)

    @property
    def completed(self) -> bool:
        return self.status.terminal or self.remaining_quantity <= 0

    @property
    def notional(self) -> float:
        return round(self.quantity * self.price, 8)

    @property
    def filled_notional(self) -> float:
        return round(self.filled_quantity * self.average_price, 8)

    def is_completed(self) -> bool:
        return self.completed

    def update_timestamp(self) -> None:
        self.updated_at = datetime.now(timezone.utc)

    touch = update_timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "platform": self.platform,
            "market": self.market,
            "symbol": self.symbol,
            "side": self.side.value,
            "quantity": self.quantity,
            "price": self.price,
            "notional": self.notional,
            "order_type": self.order_type.value,
            "status": self.status.value,
            "time_in_force": self.time_in_force.value,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "submitted_at": self.submitted_at.isoformat() if self.submitted_at else None,
            "accepted_at": self.accepted_at.isoformat() if self.accepted_at else None,
            "executed_at": self.executed_at.isoformat() if self.executed_at else None,
            "cancelled_at": self.cancelled_at.isoformat() if self.cancelled_at else None,
            "filled_quantity": self.filled_quantity,
            "remaining_quantity": self.remaining_quantity,
            "average_price": self.average_price,
            "last_fill_price": self.last_fill_price,
            "last_fill_quantity": self.last_fill_quantity,
            "last_fill_time": (
                self.last_fill_time.isoformat() if self.last_fill_time else None
            ),
            "fees_paid": self.fees_paid,
            "retry_count": self.retry_count,
            "reject_reason": self.reject_reason,
            "cancel_reason": self.cancel_reason,
            "external_id": self.external_id,
            "client_order_id": self.client_order_id,
            "opportunity_id": self.opportunity_id,
            "leg": self.leg,
            "mode": self.mode,
            "execution_policy": self.execution_policy.value,
            "execution_targets": list(self.execution_targets),
            "twap_interval": self.twap_interval,
            "twap_slices": self.twap_slices,
            "visible_quantity": self.visible_quantity,
            "split_parts": self.split_parts,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "Order":
        if not isinstance(data, Mapping):
            raise TypeError("Order.from_dict exige um Mapping.")

        values = dict(data)

        if "id" in values and "order_id" not in values:
            values["order_id"] = values["id"]

        accepted = {
            "symbol",
            "side",
            "quantity",
            "order_type",
            "price",
            "platform",
            "market",
            "time_in_force",
            "status",
            "order_id",
            "created_at",
            "updated_at",
            "submitted_at",
            "accepted_at",
            "executed_at",
            "cancelled_at",
            "filled_quantity",
            "average_price",
            "last_fill_price",
            "last_fill_quantity",
            "last_fill_time",
            "fees_paid",
            "retry_count",
            "reject_reason",
            "cancel_reason",
            "external_id",
            "client_order_id",
            "opportunity_id",
            "leg",
            "mode",
            "execution_policy",
            "execution_targets",
            "twap_interval",
            "twap_slices",
            "visible_quantity",
            "split_parts",
            "metadata",
        }

        return cls(
            **{
                key: value
                for key, value in values.items()
                if key in accepted
            }
        )

    def __getitem__(self, key: str) -> Any:
        if hasattr(self, key):
            return getattr(self, key)
        if key in self.metadata:
            return self.metadata[key]
        raise KeyError(key)

    def get(self, key: str, default: Any = None) -> Any:
        try:
            return self[key]
        except KeyError:
            return default

    def __repr__(self) -> str:
        return (
            "<Order "
            f"id={self.id} "
            f"platform={self.platform!r} "
            f"symbol={self.symbol!r} "
            f"side={self.side.value} "
            f"qty={self.quantity} "
            f"filled={self.filled_quantity} "
            f"status={self.status.value}>"
        )
