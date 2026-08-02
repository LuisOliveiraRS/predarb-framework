"""Conector CEX público falso e determinístico.

Serve para exercitar o domínio sem rede. Os dados são fixos e
gerados a partir de um preço base, para que os testes não
dependam de internet, conforme a seção 28 do CLAUDE.md.

Não possui, e não deve ganhar, qualquer método de execução: o
registry recusaria o registro.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import AsyncIterator

from app.crypto_arbitrage.domain.enums import (
    ConnectorState,
    InstrumentStatus,
    MarketType,
)
from app.crypto_arbitrage.domain.models import (
    ConnectorHealth,
    Instrument,
    OrderBookLevel,
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.symbols import (
    SymbolPair,
    parse_symbol,
)


DEFAULT_TICK = Decimal("0.01")
DEFAULT_STEP = Decimal("0.00001")
DEFAULT_SPREAD = Decimal("1")


class MockPublicCexConnector:
    """Implementa `PublicCexConnector` com dados sintéticos."""

    def __init__(
        self,
        venue_id: str,
        *,
        symbols: dict[str, Decimal] | None = None,
        clock: datetime | None = None,
        state: ConnectorState = ConnectorState.READY,
        depth_levels: int = 5,
    ) -> None:
        self.venue_id = str(venue_id).strip().upper()

        if not self.venue_id:
            raise ValueError(
                "venue_id é obrigatório."
            )

        self._symbols = dict(
            symbols
            or {"BTCUSDT": Decimal("60000")}
        )

        self._clock = clock or datetime(
            2026,
            8,
            2,
            0,
            0,
            0,
            tzinfo=timezone.utc,
        )

        self._state = state
        self._depth_levels = int(depth_levels)
        self.order_book_calls = 0

    def _pair(self, instrument_id: str) -> SymbolPair:
        return parse_symbol(instrument_id)

    async def list_instruments(self) -> list[Instrument]:
        return [
            Instrument(
                venue_id=self.venue_id,
                instrument_id=instrument_id,
                pair=self._pair(instrument_id),
                market_type=MarketType.SPOT,
                price_tick=DEFAULT_TICK,
                quantity_step=DEFAULT_STEP,
                min_quantity=Decimal("0.0001"),
                min_notional=Decimal("10"),
                status=InstrumentStatus.TRADING,
            )
            for instrument_id in sorted(self._symbols)
        ]

    async def get_order_book(
        self,
        instrument_id: str,
        depth: int,
    ) -> OrderBookSnapshot:
        self.order_book_calls += 1

        normalized = str(instrument_id).strip().upper()

        if normalized not in self._symbols:
            raise KeyError(
                f"Instrumento desconhecido: {instrument_id}."
            )

        base_price = self._symbols[normalized]
        levels = min(int(depth), self._depth_levels)

        if levels <= 0:
            raise ValueError(
                "depth deve ser maior que zero."
            )

        half_spread = DEFAULT_SPREAD / Decimal("2")

        bids = tuple(
            OrderBookLevel(
                price=(
                    base_price
                    - half_spread
                    - Decimal(index) * DEFAULT_SPREAD
                ),
                quantity=Decimal("0.5")
                + Decimal(index) * Decimal("0.25"),
            )
            for index in range(levels)
        )

        asks = tuple(
            OrderBookLevel(
                price=(
                    base_price
                    + half_spread
                    + Decimal(index) * DEFAULT_SPREAD
                ),
                quantity=Decimal("0.5")
                + Decimal(index) * Decimal("0.25"),
            )
            for index in range(levels)
        )

        return OrderBookSnapshot(
            venue_id=self.venue_id,
            instrument_id=normalized,
            bids=bids,
            asks=asks,
            exchange_timestamp=self._clock,
            received_timestamp=(
                self._clock + timedelta(milliseconds=25)
            ),
            sequence=self.order_book_calls,
        )

    async def stream_order_books(
        self,
        instruments: list[str],
    ) -> AsyncIterator[OrderBookSnapshot]:
        for instrument_id in instruments:
            yield await self.get_order_book(
                instrument_id,
                self._depth_levels,
            )

    async def get_server_time(self) -> int:
        return int(self._clock.timestamp() * 1000)

    async def health(self) -> ConnectorHealth:
        return ConnectorHealth(
            venue_id=self.venue_id,
            state=self._state,
            last_message_at=self._clock,
        )
