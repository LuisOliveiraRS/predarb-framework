"""Scanner de arbitragem espacial entre CEXs.

Seção 10 do CLAUDE.md: comprar numa venue e vender em outra, com
capital pré-posicionado nas duas pontas.

O scanner avalia **pares ordenados** de venues, porque comprar na
A e vender na B é uma oportunidade diferente de comprar na B e
vender na A, com custos e profundidades próprios.

Cada rejeição carrega o motivo. "Não achei nada" é resposta
inútil quando se investiga por que o sistema ficou parado a
manhã inteira; "book da OKX stale há 4s" e "taxa da Bybit
desconhecida" levam a ações diferentes.

Nada aqui executa. As oportunidades produzidas nascem com
`RiskStatus.BLOCKED` e `is_executable` falso.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from itertools import permutations
from typing import Any, Mapping

from app.crypto_arbitrage.domain.enums import (
    RiskStatus,
    Side,
    StrategyType,
)
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
    DomainValidationError,
    FeeUnknownError,
    InsufficientDepthError,
)
from app.crypto_arbitrage.domain.fees import FeeSchedule
from app.crypto_arbitrage.domain.models import (
    Opportunity,
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.money import (
    DecimalInput,
    ensure_positive,
)
from app.crypto_arbitrage.domain.symbols import SymbolPair
from app.crypto_arbitrage.market_data.freshness import (
    FreshnessPolicy,
)
from app.crypto_arbitrage.opportunities.profitability import (
    CostModel,
    ProfitBreakdown,
    compute_breakdown,
    meets_thresholds,
    resolve_taker_rates,
)


@dataclass(frozen=True, slots=True)
class RejectedRoute:
    """Par de venues descartado, com a razão preservada."""

    buy_venue_id: str
    sell_venue_id: str
    reason: str
    stage: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "buy_venue_id": self.buy_venue_id,
            "sell_venue_id": self.sell_venue_id,
            "reason": self.reason,
            "stage": self.stage,
        }


@dataclass(frozen=True, slots=True)
class ScoredOpportunity:
    """Oportunidade acompanhada da decomposição de custos."""

    opportunity: Opportunity
    breakdown: ProfitBreakdown

    @property
    def expected_net_profit(self) -> Decimal:
        return self.breakdown.expected_net_profit

    def to_dict(self) -> dict[str, Any]:
        payload = self.opportunity.to_dict()
        payload["breakdown"] = self.breakdown.to_dict()

        return payload


@dataclass(frozen=True, slots=True)
class ScanReport:
    """Resultado completo de uma varredura."""

    pair: SymbolPair
    requested_quantity: Decimal
    scanned_at: datetime
    opportunities: tuple[ScoredOpportunity, ...] = ()
    rejected: tuple[RejectedRoute, ...] = ()
    venues_considered: tuple[str, ...] = ()

    @property
    def best(self) -> ScoredOpportunity | None:
        return (
            self.opportunities[0]
            if self.opportunities
            else None
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "pair": self.pair.to_dict(),
            "requested_quantity": str(
                self.requested_quantity
            ),
            "scanned_at": self.scanned_at.isoformat(),
            "venues_considered": list(
                self.venues_considered
            ),
            "opportunities": [
                item.to_dict()
                for item in self.opportunities
            ],
            "rejected": [
                item.to_dict() for item in self.rejected
            ],
            "opportunity_count": len(self.opportunities),
            "rejected_count": len(self.rejected),
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "automatic_execution_authorized": False,
            "order_submission_available": False,
        }


class CexCexScanner:
    """Compara books de várias venues para o mesmo par."""

    def __init__(
        self,
        *,
        fee_schedule: FeeSchedule,
        cost_model: CostModel | None = None,
        freshness: FreshnessPolicy | None = None,
    ) -> None:
        self.fee_schedule = fee_schedule
        self.cost_model = cost_model or CostModel.create()
        self.freshness = (
            freshness or FreshnessPolicy.create()
        )

    def scan(
        self,
        *,
        pair: SymbolPair,
        quantity: DecimalInput,
        books: Mapping[str, OrderBookSnapshot],
        now: datetime,
    ) -> ScanReport:
        """Varre todos os pares ordenados de venues."""

        amount = ensure_positive(
            quantity,
            field_name="quantity",
        )

        if now.tzinfo is None:
            raise DomainValidationError(
                "now deve ter timezone."
            )

        fresh_books, rejected = self._filter_fresh(
            books,
            now=now,
        )

        scored: list[ScoredOpportunity] = []

        for buy_venue, sell_venue in permutations(
            sorted(fresh_books),
            2,
        ):
            outcome = self._evaluate_route(
                pair=pair,
                quantity=amount,
                buy_book=fresh_books[buy_venue],
                sell_book=fresh_books[sell_venue],
                now=now,
            )

            if isinstance(outcome, RejectedRoute):
                rejected.append(outcome)
                continue

            scored.append(outcome)

        scored.sort(
            key=lambda item: item.expected_net_profit,
            reverse=True,
        )

        return ScanReport(
            pair=pair,
            requested_quantity=amount,
            scanned_at=now,
            opportunities=tuple(scored),
            rejected=tuple(rejected),
            venues_considered=tuple(sorted(books)),
        )

    def _filter_fresh(
        self,
        books: Mapping[str, OrderBookSnapshot],
        *,
        now: datetime,
    ) -> tuple[
        dict[str, OrderBookSnapshot],
        list[RejectedRoute],
    ]:
        """Descarta books velhos antes de qualquer cálculo.

        Invariante 14 da seção 8: book stale não pode gerar
        ordem. Filtrar antes evita gastar cálculo em dado que
        seria rejeitado no fim.
        """

        fresh: dict[str, OrderBookSnapshot] = {}
        rejected: list[RejectedRoute] = []

        for venue_id, snapshot in books.items():
            verdict = self.freshness.evaluate(snapshot, now)

            if verdict.is_fresh:
                fresh[venue_id] = snapshot
                continue

            rejected.append(
                RejectedRoute(
                    buy_venue_id=venue_id,
                    sell_venue_id=venue_id,
                    reason=verdict.reason,
                    stage="freshness",
                )
            )

        return (fresh, rejected)

    def _evaluate_route(
        self,
        *,
        pair: SymbolPair,
        quantity: Decimal,
        buy_book: OrderBookSnapshot,
        sell_book: OrderBookSnapshot,
        now: datetime,
    ) -> ScoredOpportunity | RejectedRoute:
        buy_venue = buy_book.venue_id
        sell_venue = sell_book.venue_id

        try:
            buy_side = buy_book.vwap_for_quantity(
                Side.BUY,
                quantity,
            )

            sell_side = sell_book.vwap_for_quantity(
                Side.SELL,
                quantity,
            )
        except InsufficientDepthError as exc:
            return RejectedRoute(
                buy_venue_id=buy_venue,
                sell_venue_id=sell_venue,
                reason=str(exc),
                stage="depth",
            )

        try:
            buy_rate, sell_rate = resolve_taker_rates(
                self.fee_schedule,
                buy_venue_id=buy_venue,
                buy_instrument_id=buy_book.instrument_id,
                sell_venue_id=sell_venue,
                sell_instrument_id=(
                    sell_book.instrument_id
                ),
                moment=now,
            )
        except FeeUnknownError as exc:
            return RejectedRoute(
                buy_venue_id=buy_venue,
                sell_venue_id=sell_venue,
                reason=str(exc),
                stage="fees",
            )

        breakdown = compute_breakdown(
            quantity=quantity,
            buy_vwap=buy_side.vwap,
            sell_vwap=sell_side.vwap,
            buy_fee_rate=buy_rate,
            sell_fee_rate=sell_rate,
            cost_model=self.cost_model,
        )

        approved, reason = meets_thresholds(
            breakdown,
            self.cost_model,
        )

        if not approved:
            return RejectedRoute(
                buy_venue_id=buy_venue,
                sell_venue_id=sell_venue,
                reason=reason,
                stage="profitability",
            )

        try:
            opportunity = Opportunity(
                strategy_type=(
                    StrategyType.CEX_CEX_SPATIAL
                ),
                buy_venue_id=buy_venue,
                sell_venue_id=sell_venue,
                pair=pair,
                requested_quantity=quantity,
                executable_quantity=quantity,
                buy_vwap=breakdown.buy_vwap,
                sell_vwap=breakdown.sell_vwap,
                total_fees=breakdown.total_fees,
                # O modelo da Fase 18 tem uma unica reserva.
                # Slippage e buffer operacional entram somados
                # aqui; a separacao fica no ProfitBreakdown.
                safety_buffer=breakdown.total_reserves,
                observed_at=now,
                risk_status=RiskStatus.BLOCKED,
                data_age_ms=max(
                    buy_book.age_ms(now),
                    sell_book.age_ms(now),
                ),
            )
        except CryptoArbitrageError as exc:
            return RejectedRoute(
                buy_venue_id=buy_venue,
                sell_venue_id=sell_venue,
                reason=str(exc),
                stage="modelling",
            )

        return ScoredOpportunity(
            opportunity=opportunity,
            breakdown=breakdown,
        )

    def status(self) -> dict[str, Any]:
        return {
            "strategy": StrategyType.CEX_CEX_SPATIAL.value,
            "cost_model": self.cost_model.to_dict(),
            "freshness_limit_ms": str(
                self.freshness.max_age_ms
            ),
            "known_fee_entries": len(self.fee_schedule),
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }
