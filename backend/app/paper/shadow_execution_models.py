from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping
from uuid import uuid4

from app.real_markets.models import MarketSnapshot


PROTECTED_FALSE_FLAGS = (
    "paper_execution_authorized",
    "live_authorization",
    "execution_authorized",
    "live_execution",
    "financial_execution",
    "next_step_authorized",
)


SHADOW_SAFETY_FLAGS = {
    "market_data_only": True,
    "read_only_market_access": True,
    "shadow_execution": True,
    "simulation_only": True,
    "paper_execution_authorized": False,
    "live_authorization": False,
    "execution_authorized": False,
    "live_execution": False,
    "financial_execution": False,
    "next_step_authorized": False,
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _text(
    value: Any,
    default: str = "",
) -> str:
    return str(
        default if value is None else value
    ).strip()


def _number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float:
    if isinstance(value, bool):
        raise TypeError(
            f"O campo {field_name!r} nao pode ser booleano."
        )

    try:
        resolved = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"O campo {field_name!r} deve ser numerico."
        ) from exc

    if not isfinite(resolved):
        raise ValueError(
            f"O campo {field_name!r} deve ser finito."
        )

    if (
        minimum is not None
        and resolved < minimum
    ):
        raise ValueError(
            f"O campo {field_name!r} deve ser maior "
            f"ou igual a {minimum}."
        )

    if (
        maximum is not None
        and resolved > maximum
    ):
        raise ValueError(
            f"O campo {field_name!r} deve ser menor "
            f"ou igual a {maximum}."
        )

    return resolved


def _optional_number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
    maximum: float | None = None,
) -> float | None:
    if value is None:
        return None

    return _number(
        value,
        field_name,
        minimum=minimum,
        maximum=maximum,
    )


def _validate_safety_mapping(
    payload: Mapping[str, Any],
) -> None:
    for flag in PROTECTED_FALSE_FLAGS:
        if (
            flag in payload
            and payload[flag] is not False
        ):
            raise ValueError(
                f"A flag protegida {flag!r} "
                "deve permanecer False."
            )


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowMarketReference:
    connector_id: str
    market_id: str
    market_key: str
    market_title: str
    market_status: str
    outcome_id: str
    outcome_label: str
    token_id: str | None = None
    bid: float | None = None
    ask: float | None = None
    last: float | None = None
    bid_size: float | None = None
    ask_size: float | None = None
    quote_observed_at: str | None = None
    snapshot_captured_at: str = field(
        default_factory=_utc_now
    )
    source_latency_ms: float | None = None
    raw_reference: str | None = None
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        connector_id = _text(
            self.connector_id
        )

        market_id = _text(
            self.market_id
        )

        outcome_id = _text(
            self.outcome_id
        )

        if not connector_id:
            raise ValueError(
                "connector_id e obrigatorio."
            )

        if not market_id:
            raise ValueError(
                "market_id e obrigatorio."
            )

        if not outcome_id:
            raise ValueError(
                "outcome_id e obrigatorio."
            )

        object.__setattr__(
            self,
            "connector_id",
            connector_id,
        )

        object.__setattr__(
            self,
            "market_id",
            market_id,
        )

        object.__setattr__(
            self,
            "market_key",
            _text(
                self.market_key
            )
            or f"{connector_id}:{market_id}",
        )

        object.__setattr__(
            self,
            "market_title",
            _text(
                self.market_title
            ),
        )

        object.__setattr__(
            self,
            "market_status",
            _text(
                self.market_status,
                "UNKNOWN",
            ).upper(),
        )

        object.__setattr__(
            self,
            "outcome_id",
            outcome_id,
        )

        object.__setattr__(
            self,
            "outcome_label",
            _text(
                self.outcome_label
            ),
        )

        object.__setattr__(
            self,
            "token_id",
            _text(
                self.token_id
            )
            or None,
        )

        for name in (
            "bid",
            "ask",
            "last",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(
                        self,
                        name,
                    ),
                    name,
                    minimum=0.0,
                    maximum=1.0,
                ),
            )

        for name in (
            "bid_size",
            "ask_size",
        ):
            object.__setattr__(
                self,
                name,
                _optional_number(
                    getattr(
                        self,
                        name,
                    ),
                    name,
                    minimum=0.0,
                ),
            )

        object.__setattr__(
            self,
            "source_latency_ms",
            _optional_number(
                self.source_latency_ms,
                "source_latency_ms",
                minimum=0.0,
            ),
        )

        object.__setattr__(
            self,
            "quote_observed_at",
            _text(
                self.quote_observed_at
            )
            or None,
        )

        object.__setattr__(
            self,
            "snapshot_captured_at",
            _text(
                self.snapshot_captured_at
            )
            or _utc_now(),
        )

        object.__setattr__(
            self,
            "raw_reference",
            _text(
                self.raw_reference
            )
            or None,
        )

        object.__setattr__(
            self,
            "metadata",
            deepcopy(
                dict(
                    self.metadata
                    or {}
                )
            ),
        )

        if (
            self.bid is not None
            and self.ask is not None
            and self.bid > self.ask
        ):
            raise ValueError(
                "bid nao pode ser maior que ask."
            )

    @classmethod
    def from_snapshot(
        cls,
        snapshot: MarketSnapshot,
        *,
        outcome_id: str,
    ) -> "ShadowMarketReference":
        resolved_outcome_id = _text(
            outcome_id
        )

        outcome = next(
            (
                item
                for item
                in snapshot.market.outcomes
                if (
                    item.outcome_id
                    == resolved_outcome_id
                )
            ),
            None,
        )

        if outcome is None:
            raise ValueError(
                "O outcome informado nao existe "
                "no snapshot."
            )

        quote = next(
            (
                item
                for item
                in snapshot.quotes
                if (
                    item.outcome_id
                    == resolved_outcome_id
                )
            ),
            None,
        )

        return cls(
            connector_id=(
                snapshot.market.connector_id
            ),
            market_id=(
                snapshot.market.market_id
            ),
            market_key=(
                snapshot.market.key
            ),
            market_title=(
                snapshot.market.title
            ),
            market_status=(
                snapshot.market.status
            ),
            outcome_id=(
                outcome.outcome_id
            ),
            outcome_label=(
                outcome.label
            ),
            token_id=(
                outcome.token_id
            ),
            bid=(
                quote.bid
                if quote is not None
                else None
            ),
            ask=(
                quote.ask
                if quote is not None
                else None
            ),
            last=(
                quote.last
                if quote is not None
                else None
            ),
            bid_size=(
                quote.bid_size
                if quote is not None
                else None
            ),
            ask_size=(
                quote.ask_size
                if quote is not None
                else None
            ),
            quote_observed_at=(
                quote.observed_at
                if quote is not None
                else None
            ),
            snapshot_captured_at=(
                snapshot.captured_at
            ),
            source_latency_ms=(
                snapshot.source_latency_ms
            ),
            raw_reference=(
                snapshot.raw_reference
            ),
            metadata={
                "snapshot_metadata": deepcopy(
                    snapshot.metadata
                ),
                "market_metadata": deepcopy(
                    snapshot.market.metadata
                ),
                "quote_available": (
                    quote is not None
                ),
            },
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

    def executable_price(
        self,
        side: str,
    ) -> float | None:
        resolved_side = _text(
            side
        ).upper()

        if resolved_side == "BUY":
            return self.ask

        if resolved_side == "SELL":
            return self.bid

        raise ValueError(
            "side deve ser BUY ou SELL."
        )

    def executable_size(
        self,
        side: str,
    ) -> float | None:
        resolved_side = _text(
            side
        ).upper()

        if resolved_side == "BUY":
            return self.ask_size

        if resolved_side == "SELL":
            return self.bid_size

        raise ValueError(
            "side deve ser BUY ou SELL."
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "connector_id": self.connector_id,
            "market_id": self.market_id,
            "market_key": self.market_key,
            "market_title": self.market_title,
            "market_status": self.market_status,
            "outcome_id": self.outcome_id,
            "outcome_label": self.outcome_label,
            "token_id": self.token_id,
            "bid": self.bid,
            "ask": self.ask,
            "last": self.last,
            "bid_size": self.bid_size,
            "ask_size": self.ask_size,
            "spread": self.spread,
            "quote_observed_at": (
                self.quote_observed_at
            ),
            "snapshot_captured_at": (
                self.snapshot_captured_at
            ),
            "source_latency_ms": (
                self.source_latency_ms
            ),
            "raw_reference": (
                self.raw_reference
            ),
            "metadata": deepcopy(
                self.metadata
            ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowOrderIntent:
    market: ShadowMarketReference
    side: str
    quantity: float
    requested_price: float
    opportunity_id: str = ""
    order_id: str = field(
        default_factory=lambda: str(
            uuid4()
        )
    )
    created_at: str = field(
        default_factory=_utc_now
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        side = _text(
            self.side
        ).upper()

        if side not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "side deve ser BUY ou SELL."
            )

        object.__setattr__(
            self,
            "side",
            side,
        )

        object.__setattr__(
            self,
            "quantity",
            _number(
                self.quantity,
                "quantity",
                minimum=0.00000001,
            ),
        )

        object.__setattr__(
            self,
            "requested_price",
            _number(
                self.requested_price,
                "requested_price",
                minimum=0.0,
                maximum=1.0,
            ),
        )

        object.__setattr__(
            self,
            "opportunity_id",
            _text(
                self.opportunity_id
            ),
        )

        object.__setattr__(
            self,
            "order_id",
            _text(
                self.order_id
            )
            or str(
                uuid4()
            ),
        )

        object.__setattr__(
            self,
            "created_at",
            _text(
                self.created_at
            )
            or _utc_now(),
        )

        resolved_metadata = deepcopy(
            dict(
                self.metadata
                or {}
            )
        )

        _validate_safety_mapping(
            resolved_metadata
        )

        object.__setattr__(
            self,
            "metadata",
            resolved_metadata,
        )

    @property
    def requested_notional(self) -> float:
        return round(
            self.quantity
            * self.requested_price,
            10,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "opportunity_id": (
                self.opportunity_id
            ),
            "side": self.side,
            "quantity": round(
                self.quantity,
                10,
            ),
            "requested_price": round(
                self.requested_price,
                10,
            ),
            "requested_notional": (
                self.requested_notional
            ),
            "created_at": self.created_at,
            "market": (
                self.market.to_dict()
            ),
            "metadata": deepcopy(
                self.metadata
            ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowFill:
    order_id: str
    side: str
    quantity: float
    requested_price: float
    fill_price: float
    fee_rate: float = 0.0
    fee_basis_price: float | None = None
    explicit_slippage_cost: float | None = None
    fill_id: str = field(
        default_factory=lambda: str(
            uuid4()
        )
    )
    simulated_at: str = field(
        default_factory=_utc_now
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        order_id = _text(
            self.order_id
        )

        if not order_id:
            raise ValueError(
                "order_id e obrigatorio."
            )

        side = _text(
            self.side
        ).upper()

        if side not in {
            "BUY",
            "SELL",
        }:
            raise ValueError(
                "side deve ser BUY ou SELL."
            )

        object.__setattr__(
            self,
            "order_id",
            order_id,
        )

        object.__setattr__(
            self,
            "side",
            side,
        )

        object.__setattr__(
            self,
            "quantity",
            _number(
                self.quantity,
                "quantity",
                minimum=0.00000001,
            ),
        )

        object.__setattr__(
            self,
            "requested_price",
            _number(
                self.requested_price,
                "requested_price",
                minimum=0.0,
                maximum=1.0,
            ),
        )

        object.__setattr__(
            self,
            "fill_price",
            _number(
                self.fill_price,
                "fill_price",
                minimum=0.0,
                maximum=1.0,
            ),
        )

        object.__setattr__(
            self,
            "fee_rate",
            _number(
                self.fee_rate,
                "fee_rate",
                minimum=0.0,
                maximum=1.0,
            ),
        )

        object.__setattr__(
            self,
            "fee_basis_price",
            _optional_number(
                self.fee_basis_price,
                "fee_basis_price",
                minimum=0.0,
                maximum=1.0,
            ),
        )

        object.__setattr__(
            self,
            "explicit_slippage_cost",
            _optional_number(
                self.explicit_slippage_cost,
                "explicit_slippage_cost",
                minimum=0.0,
            ),
        )

        object.__setattr__(
            self,
            "fill_id",
            _text(
                self.fill_id
            )
            or str(
                uuid4()
            ),
        )

        object.__setattr__(
            self,
            "simulated_at",
            _text(
                self.simulated_at
            )
            or _utc_now(),
        )

        resolved_metadata = deepcopy(
            dict(
                self.metadata
                or {}
            )
        )

        _validate_safety_mapping(
            resolved_metadata
        )

        object.__setattr__(
            self,
            "metadata",
            resolved_metadata,
        )

    @property
    def gross_notional(self) -> float:
        return round(
            self.quantity
            * self.fill_price,
            10,
        )

    @property
    def fee_basis_notional(self) -> float:
        basis_price = (
            self.fill_price
            if self.fee_basis_price is None
            else self.fee_basis_price
        )

        return round(
            self.quantity
            * basis_price,
            10,
        )

    @property
    def fee(self) -> float:
        return round(
            self.fee_basis_notional
            * self.fee_rate,
            10,
        )

    @property
    def additional_slippage_cost(self) -> float:
        return round(
            self.explicit_slippage_cost
            if self.explicit_slippage_cost
            is not None
            else 0.0,
            10,
        )

    @property
    def cash_flow(self) -> float:
        if self.side == "BUY":
            return round(
                -(
                    self.gross_notional
                    + self.fee
                    + self.additional_slippage_cost
                ),
                10,
            )

        return round(
            self.gross_notional
            - self.fee
            - self.additional_slippage_cost,
            10,
        )

    @property
    def slippage_amount(self) -> float:
        if self.side == "BUY":
            value = (
                self.fill_price
                - self.requested_price
            )
        else:
            value = (
                self.requested_price
                - self.fill_price
            )

        return round(
            value,
            10,
        )

    @property
    def slippage_cost(self) -> float:
        if (
            self.explicit_slippage_cost
            is not None
        ):
            return round(
                self.explicit_slippage_cost,
                10,
            )

        return round(
            self.quantity
            * self.slippage_amount,
            10,
        )

    @property
    def slippage_rate(self) -> float:
        requested_notional = (
            self.quantity
            * self.requested_price
        )

        if (
            self.explicit_slippage_cost
            is not None
        ):
            if requested_notional == 0:
                return 0.0

            return round(
                self.explicit_slippage_cost
                / requested_notional,
                10,
            )

        if self.requested_price == 0:
            return 0.0

        return round(
            self.slippage_amount
            / self.requested_price,
            10,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "side": self.side,
            "quantity": round(
                self.quantity,
                10,
            ),
            "requested_price": round(
                self.requested_price,
                10,
            ),
            "fill_price": round(
                self.fill_price,
                10,
            ),
            "gross_notional": (
                self.gross_notional
            ),
            "fee_basis_price": (
                self.fee_basis_price
            ),
            "fee_basis_notional": (
                self.fee_basis_notional
            ),
            "fee_rate": round(
                self.fee_rate,
                10,
            ),
            "fee": self.fee,
            "cash_flow": self.cash_flow,
            "slippage_amount": (
                self.slippage_amount
            ),
            "explicit_slippage_cost": (
                self.explicit_slippage_cost
            ),
            "slippage_cost": (
                self.slippage_cost
            ),
            "slippage_rate": (
                self.slippage_rate
            ),
            "simulated_at": (
                self.simulated_at
            ),
            "metadata": deepcopy(
                self.metadata
            ),
        }


@dataclass(
    frozen=True,
    slots=True,
)
class ShadowExecutionRecord:
    opportunity_id: str = ""
    status: str = "SIMULATED"
    market_references: tuple[
        ShadowMarketReference,
        ...,
    ] = field(
        default_factory=tuple
    )
    orders: tuple[
        ShadowOrderIntent,
        ...,
    ] = field(
        default_factory=tuple
    )
    fills: tuple[
        ShadowFill,
        ...,
    ] = field(
        default_factory=tuple
    )
    expected_payout: float = 0.0
    rejection_reasons: tuple[
        str,
        ...,
    ] = field(
        default_factory=tuple
    )
    execution_id: str = field(
        default_factory=lambda: str(
            uuid4()
        )
    )
    created_at: str = field(
        default_factory=_utc_now
    )
    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    VALID_STATUSES = {
        "PLANNED",
        "SIMULATED",
        "PARTIAL",
        "REJECTED",
        "OBSERVED",
    }

    def __post_init__(self) -> None:
        status = _text(
            self.status,
            "SIMULATED",
        ).upper()

        if status not in self.VALID_STATUSES:
            raise ValueError(
                "Status Shadow invalido."
            )

        object.__setattr__(
            self,
            "status",
            status,
        )

        object.__setattr__(
            self,
            "opportunity_id",
            _text(
                self.opportunity_id
            ),
        )

        object.__setattr__(
            self,
            "execution_id",
            _text(
                self.execution_id
            )
            or str(
                uuid4()
            ),
        )

        object.__setattr__(
            self,
            "created_at",
            _text(
                self.created_at
            )
            or _utc_now(),
        )

        object.__setattr__(
            self,
            "market_references",
            tuple(
                self.market_references
                or ()
            ),
        )

        object.__setattr__(
            self,
            "orders",
            tuple(
                self.orders
                or ()
            ),
        )

        object.__setattr__(
            self,
            "fills",
            tuple(
                self.fills
                or ()
            ),
        )

        object.__setattr__(
            self,
            "expected_payout",
            _number(
                self.expected_payout,
                "expected_payout",
                minimum=0.0,
            ),
        )

        rejection_reasons = tuple(
            _text(
                item
            )
            for item
            in (
                self.rejection_reasons
                or ()
            )
            if _text(
                item
            )
        )

        object.__setattr__(
            self,
            "rejection_reasons",
            rejection_reasons,
        )

        order_ids = [
            item.order_id
            for item
            in self.orders
        ]

        if (
            len(order_ids)
            != len(
                set(
                    order_ids
                )
            )
        ):
            raise ValueError(
                "order_id duplicado no registro Shadow."
            )

        allowed_order_ids = set(
            order_ids
        )

        unknown_fill_orders = sorted(
            {
                item.order_id
                for item
                in self.fills
                if (
                    item.order_id
                    not in allowed_order_ids
                )
            }
        )

        if unknown_fill_orders:
            raise ValueError(
                "Fill Shadow referencia ordem inexistente: "
                + ", ".join(
                    unknown_fill_orders
                )
            )

        resolved_metadata = deepcopy(
            dict(
                self.metadata
                or {}
            )
        )

        _validate_safety_mapping(
            resolved_metadata
        )

        object.__setattr__(
            self,
            "metadata",
            resolved_metadata,
        )

        if (
            status == "REJECTED"
            and not rejection_reasons
        ):
            raise ValueError(
                "Registro REJECTED exige "
                "rejection_reasons."
            )

    @property
    def requested_notional(self) -> float:
        return round(
            sum(
                item.requested_notional
                for item
                in self.orders
            ),
            10,
        )

    @property
    def filled_notional(self) -> float:
        return round(
            sum(
                item.gross_notional
                for item
                in self.fills
            ),
            10,
        )

    @property
    def total_fees(self) -> float:
        return round(
            sum(
                item.fee
                for item
                in self.fills
            ),
            10,
        )

    @property
    def total_slippage_cost(self) -> float:
        return round(
            sum(
                item.slippage_cost
                for item
                in self.fills
            ),
            10,
        )

    @property
    def net_cash_flow(self) -> float:
        return round(
            sum(
                item.cash_flow
                for item
                in self.fills
            ),
            10,
        )

    @property
    def simulated_profit(self) -> float:
        return round(
            self.expected_payout
            + self.net_cash_flow,
            10,
        )

    @property
    def simulated_roi(self) -> float:
        invested = max(
            0.0,
            -self.net_cash_flow,
        )

        if invested == 0:
            return 0.0

        return round(
            self.simulated_profit
            / invested,
            10,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "execution_id": (
                self.execution_id
            ),
            "opportunity_id": (
                self.opportunity_id
            ),
            "status": self.status,
            "created_at": self.created_at,
            "market_references": [
                item.to_dict()
                for item
                in self.market_references
            ],
            "orders": [
                item.to_dict()
                for item
                in self.orders
            ],
            "fills": [
                item.to_dict()
                for item
                in self.fills
            ],
            "requested_notional": (
                self.requested_notional
            ),
            "filled_notional": (
                self.filled_notional
            ),
            "total_fees": (
                self.total_fees
            ),
            "total_slippage_cost": (
                self.total_slippage_cost
            ),
            "net_cash_flow": (
                self.net_cash_flow
            ),
            "expected_payout": round(
                self.expected_payout,
                10,
            ),
            "simulated_profit": (
                self.simulated_profit
            ),
            "simulated_roi": (
                self.simulated_roi
            ),
            "rejection_reasons": list(
                self.rejection_reasons
            ),
            "metadata": deepcopy(
                self.metadata
            ),
            **deepcopy(
                SHADOW_SAFETY_FLAGS
            ),
        }

    def to_audit_payload(
        self,
    ) -> dict[str, Any]:
        payload = self.to_dict()

        _validate_safety_mapping(
            payload
        )

        return payload
