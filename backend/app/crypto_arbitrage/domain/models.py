"""Modelos imutáveis do domínio cripto.

Todos os valores financeiros são `Decimal`. Todos os modelos são
frozen: um book ou uma oportunidade não devem mudar depois de
observados, porque a decisão de risco é tomada sobre um instante
específico.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any, Sequence
from uuid import uuid4

from app.crypto_arbitrage.domain.enums import (
    ConnectorState,
    ExecutionMode,
    InstrumentStatus,
    MarketType,
    OrderType,
    RiskStatus,
    Side,
    StrategyType,
    TimeInForce,
)
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    InsufficientDepthError,
    StaleMarketDataError,
)
from app.crypto_arbitrage.domain.money import (
    ZERO,
    DecimalInput,
    ensure_non_negative,
    ensure_positive,
    to_decimal,
)
from app.crypto_arbitrage.domain.symbols import SymbolPair


def _require_text(
    value: str,
    *,
    field_name: str,
) -> str:
    normalized = str(value or "").strip()

    if not normalized:
        raise DomainValidationError(
            f"{field_name} é obrigatório."
        )

    return normalized


def _require_aware(
    value: datetime,
    *,
    field_name: str,
) -> datetime:
    if not isinstance(value, datetime):
        raise DomainValidationError(
            f"{field_name} deve ser datetime."
        )

    if value.tzinfo is None:
        raise DomainValidationError(
            f"{field_name} deve ter timezone. "
            "Timestamp ingênuo impede comparar venues."
        )

    return value.astimezone(timezone.utc)


@dataclass(frozen=True, slots=True)
class Instrument:
    """Instrumento negociável numa venue."""

    venue_id: str
    instrument_id: str
    pair: SymbolPair
    market_type: MarketType
    price_tick: Decimal
    quantity_step: Decimal
    min_quantity: Decimal
    min_notional: Decimal
    status: InstrumentStatus = InstrumentStatus.UNKNOWN
    chain_id: str | None = None
    base_token_address: str | None = None
    quote_token_address: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "venue_id",
            _require_text(
                self.venue_id,
                field_name="venue_id",
            ),
        )

        object.__setattr__(
            self,
            "instrument_id",
            _require_text(
                self.instrument_id,
                field_name="instrument_id",
            ),
        )

        for name in (
            "price_tick",
            "quantity_step",
            "min_quantity",
        ):
            object.__setattr__(
                self,
                name,
                ensure_positive(
                    getattr(self, name),
                    field_name=name,
                ),
            )

        object.__setattr__(
            self,
            "min_notional",
            ensure_non_negative(
                self.min_notional,
                field_name="min_notional",
            ),
        )

    @property
    def is_tradable(self) -> bool:
        """Só instrumento confirmado como TRADING é negociável."""

        return self.status is InstrumentStatus.TRADING

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "pair": self.pair.to_dict(),
            "market_type": self.market_type.value,
            "price_tick": str(self.price_tick),
            "quantity_step": str(self.quantity_step),
            "min_quantity": str(self.min_quantity),
            "min_notional": str(self.min_notional),
            "status": self.status.value,
            "chain_id": self.chain_id,
            "is_tradable": self.is_tradable,
        }


@dataclass(frozen=True, slots=True)
class OrderBookLevel:
    """Um nível de preço e quantidade do book."""

    price: Decimal
    quantity: Decimal

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "price",
            ensure_positive(
                self.price,
                field_name="price",
            ),
        )

        object.__setattr__(
            self,
            "quantity",
            ensure_positive(
                self.quantity,
                field_name="quantity",
            ),
        )

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "price": str(self.price),
            "quantity": str(self.quantity),
        }


@dataclass(frozen=True, slots=True)
class VwapResult:
    """Resultado de um cálculo de VWAP por profundidade."""

    vwap: Decimal
    filled_quantity: Decimal
    notional: Decimal
    levels_consumed: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "vwap": str(self.vwap),
            "filled_quantity": str(self.filled_quantity),
            "notional": str(self.notional),
            "levels_consumed": self.levels_consumed,
        }


@dataclass(frozen=True, slots=True)
class OrderBookSnapshot:
    """Foto imutável do book em um instante.

    `bids` em ordem decrescente de preço, `asks` em ordem
    crescente. A ordenação é validada, não assumida: um book
    desordenado produziria VWAP incorreto silenciosamente.
    """

    venue_id: str
    instrument_id: str
    bids: tuple[OrderBookLevel, ...]
    asks: tuple[OrderBookLevel, ...]
    exchange_timestamp: datetime
    received_timestamp: datetime
    sequence: int | None = None
    is_snapshot: bool = True
    checksum: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "venue_id",
            _require_text(
                self.venue_id,
                field_name="venue_id",
            ),
        )

        object.__setattr__(
            self,
            "instrument_id",
            _require_text(
                self.instrument_id,
                field_name="instrument_id",
            ),
        )

        object.__setattr__(
            self,
            "bids",
            tuple(self.bids),
        )

        object.__setattr__(
            self,
            "asks",
            tuple(self.asks),
        )

        _validate_ordering(
            self.bids,
            descending=True,
            side_name="bids",
        )

        _validate_ordering(
            self.asks,
            descending=False,
            side_name="asks",
        )

        object.__setattr__(
            self,
            "exchange_timestamp",
            _require_aware(
                self.exchange_timestamp,
                field_name="exchange_timestamp",
            ),
        )

        object.__setattr__(
            self,
            "received_timestamp",
            _require_aware(
                self.received_timestamp,
                field_name="received_timestamp",
            ),
        )

        if self.bids and self.asks:
            if self.bids[0].price >= self.asks[0].price:
                raise DomainValidationError(
                    "Book cruzado: melhor bid não pode ser "
                    "maior ou igual ao melhor ask."
                )

    @property
    def best_bid(self) -> OrderBookLevel | None:
        return self.bids[0] if self.bids else None

    @property
    def best_ask(self) -> OrderBookLevel | None:
        return self.asks[0] if self.asks else None

    @property
    def mid_price(self) -> Decimal | None:
        if not self.bids or not self.asks:
            return None

        return (
            self.bids[0].price + self.asks[0].price
        ) / Decimal("2")

    def age_ms(self, now: datetime) -> Decimal:
        """Idade do book em milissegundos.

        Medida contra `received_timestamp`, não contra o
        timestamp da exchange: relógios de venues divergem, e a
        idade que importa para decidir é desde que o dado chegou.
        """

        reference = _require_aware(
            now,
            field_name="now",
        )

        delta = reference - self.received_timestamp

        return to_decimal(
            str(delta.total_seconds() * 1000),
            field_name="age_ms",
        )

    def is_stale(
        self,
        now: datetime,
        max_age_ms: DecimalInput,
    ) -> bool:
        limit = ensure_positive(
            max_age_ms,
            field_name="max_age_ms",
        )

        return self.age_ms(now) > limit

    def require_fresh(
        self,
        now: datetime,
        max_age_ms: DecimalInput,
    ) -> None:
        """Levanta erro se o book estiver velho demais.

        Invariante 14 da seção 8 do CLAUDE.md.
        """

        if self.is_stale(now, max_age_ms):
            raise StaleMarketDataError(
                f"Book de {self.venue_id}/"
                f"{self.instrument_id} com "
                f"{self.age_ms(now)}ms excede o limite de "
                f"{max_age_ms}ms."
            )

    def vwap_for_quantity(
        self,
        side: Side,
        quantity: DecimalInput,
    ) -> VwapResult:
        """VWAP executável para consumir `quantity` do book.

        `Side.BUY` consome asks, `Side.SELL` consome bids. Não
        compara last price: a seção 15 do CLAUDE.md exige preço
        executável por profundidade.
        """

        target = ensure_positive(
            quantity,
            field_name="quantity",
        )

        levels = (
            self.asks
            if side is Side.BUY
            else self.bids
        )

        remaining = target
        notional = ZERO
        consumed = 0

        for level in levels:
            if remaining <= ZERO:
                break

            take = min(remaining, level.quantity)
            notional += take * level.price
            remaining -= take
            consumed += 1

        if remaining > ZERO:
            available = target - remaining

            raise InsufficientDepthError(
                f"Profundidade insuficiente em "
                f"{self.venue_id}/{self.instrument_id} "
                f"para {target}. Disponível: {available}."
            )

        return VwapResult(
            vwap=notional / target,
            filled_quantity=target,
            notional=notional,
            levels_consumed=consumed,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "bids": [level.to_dict() for level in self.bids],
            "asks": [level.to_dict() for level in self.asks],
            "sequence": self.sequence,
            "exchange_timestamp": (
                self.exchange_timestamp.isoformat()
            ),
            "received_timestamp": (
                self.received_timestamp.isoformat()
            ),
            "is_snapshot": self.is_snapshot,
            "checksum": self.checksum,
        }


def _validate_ordering(
    levels: Sequence[OrderBookLevel],
    *,
    descending: bool,
    side_name: str,
) -> None:
    for previous, current in zip(levels, levels[1:]):
        out_of_order = (
            previous.price <= current.price
            if descending
            else previous.price >= current.price
        )

        if out_of_order:
            raise DomainValidationError(
                f"{side_name} fora de ordem em "
                f"{previous.price} -> {current.price}."
            )


@dataclass(frozen=True, slots=True)
class ConnectorHealth:
    """Saúde observável de um conector de dados."""

    venue_id: str
    state: ConnectorState
    last_message_at: datetime | None = None
    gap_count: int = 0
    reconnect_count: int = 0
    detail: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "state": self.state.value,
            "last_message_at": (
                self.last_message_at.isoformat()
                if self.last_message_at is not None
                else None
            ),
            "gap_count": self.gap_count,
            "reconnect_count": self.reconnect_count,
            "detail": self.detail,
            "is_usable": self.state.is_usable,
        }


@dataclass(frozen=True, slots=True)
class Balance:
    """Saldo de um ativo numa venue."""

    venue_id: str
    asset: str
    available: Decimal
    reserved: Decimal = ZERO

    def __post_init__(self) -> None:
        for name in ("available", "reserved"):
            object.__setattr__(
                self,
                name,
                ensure_non_negative(
                    getattr(self, name),
                    field_name=name,
                ),
            )

    @property
    def total(self) -> Decimal:
        return self.available + self.reserved

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "asset": self.asset,
            "available": str(self.available),
            "reserved": str(self.reserved),
            "total": str(self.total),
        }


@dataclass(frozen=True, slots=True)
class RiskDecision:
    """Decisão de risco sobre uma oportunidade.

    O default é bloqueio. Aprovar exige `approved=True` explícito
    e lista de checagens realizadas.
    """

    approved: bool = False
    status: RiskStatus = RiskStatus.BLOCKED
    reasons: tuple[str, ...] = ()
    market_data_age_ms: Decimal | None = None
    checks: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "reasons",
            tuple(self.reasons),
        )

        object.__setattr__(
            self,
            "checks",
            tuple(self.checks),
        )

        if self.approved and self.status is not (
            RiskStatus.ELIGIBLE
        ):
            raise DomainValidationError(
                "Decisão aprovada exige status ELIGIBLE."
            )

        if (
            self.status is RiskStatus.ELIGIBLE
            and not self.approved
        ):
            raise DomainValidationError(
                "Status ELIGIBLE exige approved=True."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": self.approved,
            "status": self.status.value,
            "reasons": list(self.reasons),
            "market_data_age_ms": (
                str(self.market_data_age_ms)
                if self.market_data_age_ms is not None
                else None
            ),
            "checks": list(self.checks),
        }


@dataclass(frozen=True, slots=True)
class Opportunity:
    """Ineficiência observada entre duas venues.

    Observada, não executável. `risk_status` nasce `BLOCKED` e só
    muda por decisão de risco explícita, que a Fase 18 não
    implementa.
    """

    strategy_type: StrategyType
    buy_venue_id: str
    sell_venue_id: str
    pair: SymbolPair
    requested_quantity: Decimal
    executable_quantity: Decimal
    buy_vwap: Decimal
    sell_vwap: Decimal
    total_fees: Decimal
    safety_buffer: Decimal
    observed_at: datetime
    opportunity_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    risk_status: RiskStatus = RiskStatus.BLOCKED
    data_age_ms: Decimal | None = None

    def __post_init__(self) -> None:
        if self.buy_venue_id == self.sell_venue_id:
            raise DomainValidationError(
                "Venues de compra e venda devem ser "
                "diferentes."
            )

        for name in (
            "requested_quantity",
            "executable_quantity",
            "buy_vwap",
            "sell_vwap",
        ):
            object.__setattr__(
                self,
                name,
                ensure_positive(
                    getattr(self, name),
                    field_name=name,
                ),
            )

        for name in ("total_fees", "safety_buffer"):
            object.__setattr__(
                self,
                name,
                ensure_non_negative(
                    getattr(self, name),
                    field_name=name,
                ),
            )

        if self.executable_quantity > self.requested_quantity:
            raise DomainValidationError(
                "executable_quantity não pode superar "
                "requested_quantity."
            )

        object.__setattr__(
            self,
            "observed_at",
            _require_aware(
                self.observed_at,
                field_name="observed_at",
            ),
        )

    @property
    def gross_profit(self) -> Decimal:
        return (
            self.sell_vwap - self.buy_vwap
        ) * self.executable_quantity

    @property
    def expected_net_profit(self) -> Decimal:
        """Lucro esperado após taxas e buffer de segurança.

        Não é promessa de lucro. Pode virar prejuízo por
        slippage, latência, fill parcial ou falha de API.
        """

        return (
            self.gross_profit
            - self.total_fees
            - self.safety_buffer
        )

    @property
    def is_profitable_on_paper(self) -> bool:
        return self.expected_net_profit > ZERO

    @property
    def is_executable(self) -> bool:
        """Sempre falso na Fase 18.

        Executabilidade exige decisão de risco aprovada, que
        ainda não existe. Mantido explícito para que nenhum
        chamador precise inferir.
        """

        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "opportunity_id": self.opportunity_id,
            "strategy_type": self.strategy_type.value,
            "buy_venue_id": self.buy_venue_id,
            "sell_venue_id": self.sell_venue_id,
            "pair": self.pair.to_dict(),
            "requested_quantity": str(
                self.requested_quantity
            ),
            "executable_quantity": str(
                self.executable_quantity
            ),
            "buy_vwap": str(self.buy_vwap),
            "sell_vwap": str(self.sell_vwap),
            "gross_profit": str(self.gross_profit),
            "total_fees": str(self.total_fees),
            "safety_buffer": str(self.safety_buffer),
            "expected_net_profit": str(
                self.expected_net_profit
            ),
            "risk_status": self.risk_status.value,
            "data_age_ms": (
                str(self.data_age_ms)
                if self.data_age_ms is not None
                else None
            ),
            "observed_at": self.observed_at.isoformat(),
            "is_profitable_on_paper": (
                self.is_profitable_on_paper
            ),
            "is_executable": self.is_executable,
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


@dataclass(frozen=True, slots=True)
class OrderIntent:
    """Intenção de ordem. Nunca é uma ordem submetida.

    Existe para que planos possam ser simulados e auditados. A
    Fase 18 não possui nenhum caminho que transforme uma intenção
    em ordem real.
    """

    venue_id: str
    instrument_id: str
    side: Side
    order_type: OrderType
    quantity: Decimal
    client_order_id: str = field(
        default_factory=lambda: f"predarb-{uuid4()}"
    )
    limit_price: Decimal | None = None
    time_in_force: TimeInForce = TimeInForce.IOC
    reduce_only: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "quantity",
            ensure_positive(
                self.quantity,
                field_name="quantity",
            ),
        )

        if self.order_type is OrderType.LIMIT:
            if self.limit_price is None:
                raise DomainValidationError(
                    "Ordem LIMIT exige limit_price."
                )

            object.__setattr__(
                self,
                "limit_price",
                ensure_positive(
                    self.limit_price,
                    field_name="limit_price",
                ),
            )

        if not str(self.client_order_id).strip():
            raise DomainValidationError(
                "client_order_id é obrigatório. "
                "Invariante 12 da seção 8 do CLAUDE.md."
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "client_order_id": self.client_order_id,
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "order_type": self.order_type.value,
            "quantity": str(self.quantity),
            "limit_price": (
                str(self.limit_price)
                if self.limit_price is not None
                else None
            ),
            "time_in_force": self.time_in_force.value,
            "reduce_only": self.reduce_only,
            "submitted": False,
            "order_submission_available": False,
        }


@dataclass(frozen=True, slots=True)
class ExecutionPlan:
    """Plano de execução simulado.

    `execution_mode` nunca pode ser `LIVE` nesta fase. A
    validação é do próprio modelo, não de quem o constrói.
    """

    opportunity_id: str
    legs: tuple[OrderIntent, ...]
    execution_mode: ExecutionMode = ExecutionMode.PAPER
    minimum_expected_profit: Decimal = ZERO
    plan_id: str = field(
        default_factory=lambda: str(uuid4())
    )
    risk_decision: RiskDecision = field(
        default_factory=RiskDecision
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "legs",
            tuple(self.legs),
        )

        if not self.legs:
            raise DomainValidationError(
                "Plano exige ao menos uma perna."
            )

        if self.execution_mode is ExecutionMode.LIVE:
            raise DomainValidationError(
                "Execução LIVE não é permitida. Exige "
                "autorização explícita e o checklist da "
                "seção 26 do CLAUDE.md."
            )

        object.__setattr__(
            self,
            "minimum_expected_profit",
            ensure_non_negative(
                self.minimum_expected_profit,
                field_name="minimum_expected_profit",
            ),
        )

        identifiers = [
            leg.client_order_id for leg in self.legs
        ]

        if len(set(identifiers)) != len(identifiers):
            raise DomainValidationError(
                "client_order_id duplicado entre pernas "
                "quebra a idempotência."
            )

    @property
    def is_authorized(self) -> bool:
        return False

    def to_dict(self) -> dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "opportunity_id": self.opportunity_id,
            "legs": [leg.to_dict() for leg in self.legs],
            "execution_mode": self.execution_mode.value,
            "minimum_expected_profit": str(
                self.minimum_expected_profit
            ),
            "risk_decision": self.risk_decision.to_dict(),
            "is_authorized": self.is_authorized,
            "execution_authorized": False,
            "financial_execution": False,
        }


@dataclass(frozen=True, slots=True)
class Fill:
    """Preenchimento observado. Na Fase 18, sempre simulado."""

    venue_id: str
    instrument_id: str
    side: Side
    price: Decimal
    quantity: Decimal
    fee: Decimal
    fee_asset: str
    filled_at: datetime
    client_order_id: str | None = None
    trade_id: str | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "price",
            ensure_positive(
                self.price,
                field_name="price",
            ),
        )

        object.__setattr__(
            self,
            "quantity",
            ensure_positive(
                self.quantity,
                field_name="quantity",
            ),
        )

        object.__setattr__(
            self,
            "fee",
            ensure_non_negative(
                self.fee,
                field_name="fee",
            ),
        )

        object.__setattr__(
            self,
            "filled_at",
            _require_aware(
                self.filled_at,
                field_name="filled_at",
            ),
        )

    @property
    def notional(self) -> Decimal:
        return self.price * self.quantity

    def to_dict(self) -> dict[str, Any]:
        return {
            "venue_id": self.venue_id,
            "instrument_id": self.instrument_id,
            "side": self.side.value,
            "price": str(self.price),
            "quantity": str(self.quantity),
            "notional": str(self.notional),
            "fee": str(self.fee),
            "fee_asset": self.fee_asset,
            "filled_at": self.filled_at.isoformat(),
            "client_order_id": self.client_order_id,
            "trade_id": self.trade_id,
            "simulated": True,
        }
