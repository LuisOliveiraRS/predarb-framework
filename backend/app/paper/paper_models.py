from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4


def utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def number(value: Any, field_name: str, *, minimum: float | None = None) -> float:
    if isinstance(value, bool):
        raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
    try:
        parsed = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc
    if not isfinite(parsed):
        raise ValueError(f"O campo {field_name!r} deve ser finito.")
    if minimum is not None and parsed < minimum:
        raise ValueError(
            f"O campo {field_name!r} deve ser maior ou igual a {minimum}."
        )
    return parsed


def text(value: Any, default: str = "") -> str:
    return str(default if value is None else value).strip()


@dataclass(slots=True)
class PaperTrade:
    id: str = field(default_factory=lambda: str(uuid4()))
    execution_id: str = ""
    order_id: str = ""
    opportunity_id: str = ""
    platform: str = ""
    symbol: str = ""
    market: str = ""
    leg: str = ""
    side: str = "BUY"
    quantity: float = 0.0
    price: float = 0.0
    fee: float = 0.0
    gross_notional: float = 0.0
    cash_flow: float = 0.0
    executed_at: str = field(default_factory=utc_iso)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = text(self.id) or str(uuid4())
        self.execution_id = text(self.execution_id)
        self.order_id = text(self.order_id)
        self.opportunity_id = text(self.opportunity_id)
        self.platform = text(self.platform)
        self.symbol = text(self.symbol)
        self.market = text(self.market or self.symbol)
        self.leg = text(self.leg).upper()
        self.side = text(self.side, "BUY").upper()
        if self.side not in {"BUY", "SELL"}:
            raise ValueError("PaperTrade aceita somente BUY ou SELL.")
        self.quantity = number(self.quantity, "quantity", minimum=0.0)
        self.price = number(self.price, "price", minimum=0.0)
        self.fee = number(self.fee, "fee", minimum=0.0)
        self.gross_notional = number(
            self.gross_notional or self.quantity * self.price,
            "gross_notional",
            minimum=0.0,
        )
        self.cash_flow = number(self.cash_flow, "cash_flow")
        if self.quantity <= 0:
            raise ValueError("A quantidade do PaperTrade deve ser maior que zero.")
        if not 0 <= self.price <= 1:
            raise ValueError("O preço paper deve estar entre 0 e 1.")
        self.executed_at = text(self.executed_at) or utc_iso()
        self.metadata = dict(self.metadata or {})

    @property
    def position_key(self) -> str:
        parts = (
            self.platform.casefold(),
            (self.symbol or self.market).casefold(),
            self.leg.casefold(),
        )
        return "|".join(parts)

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "execution_id": self.execution_id,
            "order_id": self.order_id,
            "opportunity_id": self.opportunity_id,
            "platform": self.platform,
            "symbol": self.symbol,
            "market": self.market,
            "leg": self.leg,
            "side": self.side,
            "quantity": round(self.quantity, 8),
            "price": round(self.price, 8),
            "fee": round(self.fee, 8),
            "gross_notional": round(self.gross_notional, 8),
            "cash_flow": round(self.cash_flow, 8),
            "executed_at": self.executed_at,
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PaperTrade":
        return cls(**dict(data))


@dataclass(slots=True)
class PaperPosition:
    id: str = field(default_factory=lambda: str(uuid4()))
    key: str = ""
    platform: str = ""
    symbol: str = ""
    market: str = ""
    leg: str = ""
    quantity: float = 0.0
    average_price: float = 0.0
    entry_fees: float = 0.0
    mark_price: float = 0.0
    realized_pnl: float = 0.0
    status: str = "OPEN"
    opened_at: str = field(default_factory=utc_iso)
    updated_at: str = field(default_factory=utc_iso)
    closed_at: str | None = None
    order_ids: list[str] = field(default_factory=list)
    opportunity_ids: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.id = text(self.id) or str(uuid4())
        self.platform = text(self.platform)
        self.symbol = text(self.symbol)
        self.market = text(self.market or self.symbol)
        self.leg = text(self.leg).upper()
        self.key = text(self.key) or "|".join(
            (
                self.platform.casefold(),
                (self.symbol or self.market).casefold(),
                self.leg.casefold(),
            )
        )
        self.quantity = number(self.quantity, "quantity", minimum=0.0)
        self.average_price = number(
            self.average_price, "average_price", minimum=0.0
        )
        self.entry_fees = number(self.entry_fees, "entry_fees", minimum=0.0)
        self.mark_price = number(self.mark_price, "mark_price", minimum=0.0)
        self.realized_pnl = number(self.realized_pnl, "realized_pnl")
        if self.average_price > 1 or self.mark_price > 1:
            raise ValueError("Preços paper devem estar entre 0 e 1.")
        self.status = text(self.status, "OPEN").upper()
        if self.status not in {"OPEN", "CLOSED"}:
            raise ValueError("Status de posição paper inválido.")
        self.opened_at = text(self.opened_at) or utc_iso()
        self.updated_at = text(self.updated_at) or self.opened_at
        self.closed_at = text(self.closed_at) or None
        self.order_ids = [text(value) for value in self.order_ids if text(value)]
        self.opportunity_ids = [
            text(value) for value in self.opportunity_ids if text(value)
        ]
        self.metadata = dict(self.metadata or {})

    @property
    def open(self) -> bool:
        return self.status == "OPEN" and self.quantity > 0

    @property
    def cost_basis(self) -> float:
        return round(self.quantity * self.average_price + self.entry_fees, 8)

    @property
    def market_value(self) -> float:
        return round(self.quantity * self.mark_price, 8)

    @property
    def unrealized_pnl(self) -> float:
        if not self.open:
            return 0.0
        return round(self.market_value - self.cost_basis, 8)

    @property
    def total_pnl(self) -> float:
        return round(self.realized_pnl + self.unrealized_pnl, 8)

    def apply_buy(self, trade: PaperTrade) -> None:
        previous_quantity = self.quantity
        new_quantity = previous_quantity + trade.quantity
        weighted_cost = (
            previous_quantity * self.average_price
            + trade.quantity * trade.price
        )
        self.quantity = new_quantity
        self.average_price = weighted_cost / new_quantity
        self.entry_fees += trade.fee
        self.mark_price = trade.price
        self.status = "OPEN"
        self.closed_at = None
        self.updated_at = trade.executed_at
        if trade.order_id and trade.order_id not in self.order_ids:
            self.order_ids.append(trade.order_id)
        if (
            trade.opportunity_id
            and trade.opportunity_id not in self.opportunity_ids
        ):
            self.opportunity_ids.append(trade.opportunity_id)

    def apply_sell(self, trade: PaperTrade) -> float:
        if trade.quantity > self.quantity + 1e-9:
            raise ValueError("Venda paper excede a posição aberta.")
        previous_quantity = self.quantity
        fee_allocation = (
            self.entry_fees * (trade.quantity / previous_quantity)
            if previous_quantity > 0
            else 0.0
        )
        realized = (
            trade.quantity * (trade.price - self.average_price)
            - fee_allocation
            - trade.fee
        )
        self.realized_pnl += realized
        self.quantity = max(0.0, previous_quantity - trade.quantity)
        self.entry_fees = max(0.0, self.entry_fees - fee_allocation)
        self.mark_price = trade.price
        self.updated_at = trade.executed_at
        if trade.order_id and trade.order_id not in self.order_ids:
            self.order_ids.append(trade.order_id)
        if self.quantity <= 1e-9:
            self.quantity = 0.0
            self.entry_fees = 0.0
            self.status = "CLOSED"
            self.closed_at = trade.executed_at
        return round(realized, 8)

    def mark(self, price: Any) -> None:
        resolved = number(price, "mark_price", minimum=0.0)
        if resolved > 1:
            raise ValueError("O mark price deve estar entre 0 e 1.")
        self.mark_price = resolved
        self.updated_at = utc_iso()

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "key": self.key,
            "platform": self.platform,
            "symbol": self.symbol,
            "market": self.market,
            "leg": self.leg,
            "quantity": round(self.quantity, 8),
            "average_price": round(self.average_price, 8),
            "entry_fees": round(self.entry_fees, 8),
            "mark_price": round(self.mark_price, 8),
            "cost_basis": self.cost_basis,
            "market_value": self.market_value,
            "realized_pnl": round(self.realized_pnl, 8),
            "unrealized_pnl": self.unrealized_pnl,
            "total_pnl": self.total_pnl,
            "status": self.status,
            "opened_at": self.opened_at,
            "updated_at": self.updated_at,
            "closed_at": self.closed_at,
            "order_ids": list(self.order_ids),
            "opportunity_ids": list(self.opportunity_ids),
            "metadata": dict(self.metadata),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "PaperPosition":
        allowed = {
            "id",
            "key",
            "platform",
            "symbol",
            "market",
            "leg",
            "quantity",
            "average_price",
            "entry_fees",
            "mark_price",
            "realized_pnl",
            "status",
            "opened_at",
            "updated_at",
            "closed_at",
            "order_ids",
            "opportunity_ids",
            "metadata",
        }
        return cls(**{key: value for key, value in data.items() if key in allowed})
