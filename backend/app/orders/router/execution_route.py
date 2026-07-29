from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True)
class ExecutionRoute:
    exchange: str
    connector: Any = None
    latency: float = 0.0
    liquidity: float = 0.0
    fee: float = 0.0
    score: float = 0.0
    allocation_quantity: float = 0.0
    expected_price: float = 0.0
    slippage_rate: float = 0.0
    slippage_amount: float = 0.0
    expected_notional: float = 0.0
    expected_fee: float = 0.0
    total_cost: float = 0.0
    enabled: bool = True
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.exchange = str(self.exchange or "").strip()
        if not self.exchange:
            raise ValueError("exchange é obrigatório para ExecutionRoute.")
        for field_name in (
            "latency",
            "liquidity",
            "fee",
            "score",
            "allocation_quantity",
            "expected_price",
            "slippage_rate",
            "slippage_amount",
            "expected_notional",
            "expected_fee",
            "total_cost",
        ):
            value = float(getattr(self, field_name))
            if field_name not in {"slippage_rate", "slippage_amount"} and value < 0:
                raise ValueError(f"{field_name} não pode ser negativo.")
            setattr(self, field_name, value)
        self.enabled = bool(self.enabled)
        self.metadata = dict(self.metadata or {})

    @property
    def name(self) -> str:
        return self.exchange

    @property
    def available(self) -> bool:
        return self.enabled and self.liquidity > 0

    @property
    def connector_name(self) -> str:
        if isinstance(self.connector, str):
            return self.connector.strip()
        return str(getattr(self.connector, "name", self.exchange) or self.exchange).strip()

    @classmethod
    def from_value(cls, value: Any) -> "ExecutionRoute":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                exchange=value.get("exchange", value.get("name", value.get("platform", ""))),
                connector=value.get("connector"),
                latency=value.get("latency", value.get("latency_ms", 0.0)),
                liquidity=value.get("liquidity", value.get("available_quantity", 0.0)),
                fee=value.get("fee", value.get("fee_rate", 0.0)),
                score=value.get("score", 0.0),
                allocation_quantity=value.get("allocation_quantity", value.get("quantity", 0.0)),
                expected_price=value.get("expected_price", value.get("price", 0.0)),
                slippage_rate=value.get("slippage_rate", 0.0),
                slippage_amount=value.get("slippage_amount", 0.0),
                expected_notional=value.get("expected_notional", value.get("notional", 0.0)),
                expected_fee=value.get("expected_fee", 0.0),
                total_cost=value.get("total_cost", 0.0),
                enabled=value.get("enabled", True),
                metadata=value.get("metadata", {}),
            )
        return cls(
            exchange=getattr(value, "exchange", getattr(value, "name", "")),
            connector=getattr(value, "connector", None),
            latency=getattr(value, "latency", 0.0),
            liquidity=getattr(value, "liquidity", 0.0),
            fee=getattr(value, "fee", 0.0),
            score=getattr(value, "score", 0.0),
            allocation_quantity=getattr(value, "allocation_quantity", getattr(value, "quantity", 0.0)),
            expected_price=getattr(value, "expected_price", getattr(value, "price", 0.0)),
            slippage_rate=getattr(value, "slippage_rate", 0.0),
            slippage_amount=getattr(value, "slippage_amount", 0.0),
            expected_notional=getattr(value, "expected_notional", 0.0),
            expected_fee=getattr(value, "expected_fee", 0.0),
            total_cost=getattr(value, "total_cost", 0.0),
            enabled=getattr(value, "enabled", True),
            metadata=getattr(value, "metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "exchange": self.exchange,
            "connector": self.connector_name,
            "latency": self.latency,
            "liquidity": self.liquidity,
            "fee": self.fee,
            "score": self.score,
            "allocation_quantity": self.allocation_quantity,
            "expected_price": self.expected_price,
            "slippage_rate": self.slippage_rate,
            "slippage_amount": self.slippage_amount,
            "expected_notional": self.expected_notional,
            "expected_fee": self.expected_fee,
            "total_cost": self.total_cost,
            "enabled": self.enabled,
            "available": self.available,
            "metadata": dict(self.metadata),
        }
