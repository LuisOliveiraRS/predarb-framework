from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Any, Iterable


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _bounded_probability(
    value: float | None,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    normalized = float(value)

    if not 0.0 <= normalized <= 1.0:
        raise ValueError(
            f"{field_name} deve estar entre 0 e 1."
        )

    return normalized


def _non_negative(
    value: float | None,
    *,
    field_name: str,
) -> float | None:
    if value is None:
        return None

    normalized = float(value)

    if normalized < 0:
        raise ValueError(
            f"{field_name} não pode ser negativo."
        )

    return normalized


@dataclass(frozen=True)
class MarketOutcome:
    outcome_id: str
    label: str
    token_id: str | None = None

    def __post_init__(self) -> None:
        if not self.outcome_id.strip():
            raise ValueError(
                "outcome_id é obrigatório."
            )

        if not self.label.strip():
            raise ValueError(
                "label do outcome é obrigatório."
            )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedMarket:
    connector_id: str
    market_id: str
    title: str
    status: str
    outcomes: tuple[MarketOutcome, ...]
    close_time: str | None = None
    currency: str = "USD"
    category: str | None = None
    source_url: str | None = None
    description: str | None = None
    observed_at: str = field(
        default_factory=utc_now
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        if not self.connector_id.strip():
            raise ValueError(
                "connector_id é obrigatório."
            )

        if not self.market_id.strip():
            raise ValueError(
                "market_id é obrigatório."
            )

        if not self.title.strip():
            raise ValueError(
                "title do mercado é obrigatório."
            )

        normalized_status = (
            self.status.strip().upper()
        )

        if normalized_status not in {
            "OPEN",
            "CLOSED",
            "RESOLVED",
            "SUSPENDED",
            "UNKNOWN",
        }:
            raise ValueError(
                "status de mercado inválido."
            )

        object.__setattr__(
            self,
            "status",
            normalized_status,
        )

        if len(self.outcomes) < 2:
            raise ValueError(
                "O mercado deve possuir pelo menos dois outcomes."
            )

        ids = [
            item.outcome_id
            for item in self.outcomes
        ]

        if len(ids) != len(set(ids)):
            raise ValueError(
                "outcome_id duplicado."
            )

    @property
    def key(self) -> str:
        return (
            f"{self.connector_id}:"
            f"{self.market_id}"
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["key"] = self.key
        return payload


@dataclass(frozen=True)
class MarketQuote:
    connector_id: str
    market_id: str
    outcome_id: str
    bid: float | None
    ask: float | None
    last: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    observed_at: str = field(
        default_factory=utc_now
    )

    def __post_init__(self) -> None:
        if not self.connector_id.strip():
            raise ValueError(
                "connector_id é obrigatório."
            )

        if not self.market_id.strip():
            raise ValueError(
                "market_id é obrigatório."
            )

        if not self.outcome_id.strip():
            raise ValueError(
                "outcome_id é obrigatório."
            )

        for name in (
            "bid",
            "ask",
            "last",
        ):
            object.__setattr__(
                self,
                name,
                _bounded_probability(
                    getattr(self, name),
                    field_name=name,
                ),
            )

        for name in (
            "bid_size",
            "ask_size",
        ):
            object.__setattr__(
                self,
                name,
                _non_negative(
                    getattr(self, name),
                    field_name=name,
                ),
            )

        if (
            self.bid is not None
            and self.ask is not None
            and self.bid > self.ask
        ):
            raise ValueError(
                "bid não pode ser maior que ask."
            )

    @property
    def spread(self) -> float | None:
        if (
            self.bid is None
            or self.ask is None
        ):
            return None

        return round(
            self.ask - self.bid,
            10,
        )

    @property
    def midpoint(self) -> float | None:
        if (
            self.bid is None
            or self.ask is None
        ):
            return None

        return round(
            (self.bid + self.ask) / 2,
            10,
        )

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["spread"] = self.spread
        payload["midpoint"] = self.midpoint
        return payload


@dataclass(frozen=True)
class MarketSnapshot:
    market: NormalizedMarket
    quotes: tuple[MarketQuote, ...]
    captured_at: str = field(
        default_factory=utc_now
    )
    source_latency_ms: float | None = None
    raw_reference: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        outcome_ids = {
            item.outcome_id
            for item in self.market.outcomes
        }

        quote_ids = [
            item.outcome_id
            for item in self.quotes
        ]

        if len(quote_ids) != len(set(quote_ids)):
            raise ValueError(
                "Quote duplicada para o mesmo outcome."
            )

        invalid = sorted(
            set(quote_ids) - outcome_ids
        )

        if invalid:
            raise ValueError(
                "Quotes usam outcomes inexistentes: "
                f"{invalid}"
            )

        if self.source_latency_ms is not None:
            if float(self.source_latency_ms) < 0:
                raise ValueError(
                    "source_latency_ms não pode ser negativo."
                )

    @property
    def key(self) -> str:
        return self.market.key

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "market": self.market.to_dict(),
            "quotes": [
                item.to_dict()
                for item in self.quotes
            ],
            "captured_at": self.captured_at,
            "source_latency_ms": (
                self.source_latency_ms
            ),
            "raw_reference": (
                self.raw_reference
            ),
            "metadata": dict(
                self.metadata
            ),
        }


@dataclass(frozen=True)
class ConnectorHealth:
    connector_id: str
    name: str
    healthy: bool
    message: str
    checked_at: str = field(
        default_factory=utc_now
    )
    read_only: bool = True
    capabilities: tuple[str, ...] = (
        "market_data",
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def serialize_markets(
    markets: Iterable[NormalizedMarket],
) -> list[dict[str, Any]]:
    return [
        item.to_dict()
        for item in markets
    ]
