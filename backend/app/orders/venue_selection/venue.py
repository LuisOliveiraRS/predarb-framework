from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from math import isfinite
from typing import Any


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
class Venue:
    """Destino elegível para roteamento de uma ordem.

    Latência usa milissegundos, fee usa taxa decimal e reliability aceita
    valores entre 0–1 ou 0–100. O objeto contém dados; não chama conectores.
    """

    name: str
    latency: float = 0.0
    fee: float = 0.0
    liquidity: float = 0.0
    reliability: float = 1.0
    enabled: bool = True
    connector: Any = None
    bid: float = 0.0
    ask: float = 0.0
    score: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.name = str(self.name or "").strip()
        if not self.name:
            raise ValueError("name é obrigatório para Venue.")
        self.latency = _number(self.latency, "latency")
        self.fee = _number(self.fee, "fee")
        self.liquidity = _number(self.liquidity, "liquidity")
        self.reliability = _number(self.reliability, "reliability")
        self.bid = _number(self.bid, "bid")
        self.ask = _number(self.ask, "ask")
        self.score = _number(self.score, "score")
        self.enabled = bool(self.enabled)
        self.metadata = dict(self.metadata or {})

    @property
    def available(self) -> bool:
        return self.enabled and self.reliability > 0

    @property
    def available_quantity(self) -> float:
        return self.liquidity

    @property
    def connector_name(self) -> str:
        if isinstance(self.connector, str):
            return self.connector.strip()
        name = getattr(self.connector, "name", None)
        return str(name or self.name).strip()

    @classmethod
    def from_value(cls, value: Any) -> "Venue":
        if isinstance(value, cls):
            return value
        if isinstance(value, Mapping):
            return cls(
                name=value.get("name", value.get("exchange", value.get("platform", ""))),
                latency=value.get("latency", value.get("latency_ms", 0.0)),
                fee=value.get("fee", value.get("fee_rate", 0.0)),
                liquidity=value.get(
                    "liquidity",
                    value.get("quantity", value.get("available_quantity", 0.0)),
                ),
                reliability=value.get(
                    "reliability",
                    value.get("success_rate", 1.0),
                ),
                enabled=value.get("enabled", True),
                connector=value.get("connector"),
                bid=value.get("bid", 0.0),
                ask=value.get("ask", 0.0),
                score=value.get("score", 0.0),
                metadata=value.get("metadata", {}),
            )
        return cls(
            name=getattr(value, "name", getattr(value, "exchange", "")),
            latency=getattr(value, "latency", getattr(value, "latency_ms", 0.0)),
            fee=getattr(value, "fee", getattr(value, "fee_rate", 0.0)),
            liquidity=getattr(
                value,
                "liquidity",
                getattr(value, "quantity", getattr(value, "available_quantity", 0.0)),
            ),
            reliability=getattr(
                value,
                "reliability",
                getattr(value, "success_rate", 1.0),
            ),
            enabled=getattr(value, "enabled", True),
            connector=getattr(value, "connector", None),
            bid=getattr(value, "bid", 0.0),
            ask=getattr(value, "ask", 0.0),
            score=getattr(value, "score", 0.0),
            metadata=getattr(value, "metadata", {}),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "latency": self.latency,
            "fee": self.fee,
            "liquidity": self.liquidity,
            "reliability": self.reliability,
            "enabled": self.enabled,
            "available": self.available,
            "connector": self.connector_name,
            "bid": self.bid,
            "ask": self.ask,
            "score": self.score,
            "metadata": dict(self.metadata),
        }
