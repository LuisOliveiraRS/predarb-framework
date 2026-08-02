"""Tradução dos formatos públicos da Bybit V5 Spot.

Formatos confirmados na documentação oficial em 02/08/2026:
`/v5/market/instruments-info?category=spot` e o tópico WebSocket
`orderbook.<depth>.<symbol>`.

Garantia de integridade mais fraca que Binance e OKX, e isso é
deliberado, não descuido. A documentação da Bybit:

- **não afirma** que `u` incrementa de um em um entre deltas;
- **não descreve** método para detectar mensagem perdida;
- diz que `seq` serve para comparar níveis de profundidade entre
  si, não para achar buraco;
- em nível 1, reenvia snapshot com o **mesmo** `u` quando nada
  muda por três segundos.

Presumir `STRICT_INCREMENT` inventaria uma garantia que a venue
não oferece e produziria alarme falso de gap em operação normal.
Daí `SequenceMode.MONOTONIC`: exige apenas avanço, sem alegar
detecção de gap.

A integridade fica por conta dos sinais que a Bybit de fato
documenta: `type == "snapshot"` obriga reset, `u == 1` indica
reinício de serviço e também obriga reset, e o próprio livro
levanta erro se cruzar.
"""

from __future__ import annotations

from typing import Any

from app.crypto_arbitrage.connectors.venue_adapter import (
    InstrumentParseResult,
    SkippedInstrument,
    SnapshotPayload,
    StreamMessage,
    StreamMessageKind,
    coerce_int,
    milliseconds_to_datetime,
    parse_levels,
    require_mapping,
    require_sequence,
)
from app.crypto_arbitrage.domain.enums import (
    InstrumentStatus,
    MarketType,
)
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
    DomainValidationError,
)
from app.crypto_arbitrage.domain.models import Instrument
from app.crypto_arbitrage.domain.symbols import build_pair
from app.crypto_arbitrage.market_data.local_book import (
    BookUpdate,
    SequenceMode,
)


STATUS_MAP: dict[str, InstrumentStatus] = {
    "trading": InstrumentStatus.TRADING,
    "prelaunch": InstrumentStatus.UNKNOWN,
    "delivering": InstrumentStatus.HALTED,
    "closed": InstrumentStatus.DELISTED,
}

# Reinicio de servico: a Bybit reenvia o livro inteiro com u=1.
SERVICE_RESTART_UPDATE_ID = 1


class BybitSpotAdapter:
    """Adaptador read-only da Bybit V5 Spot."""

    venue_id = "BYBIT"
    sequence_mode = SequenceMode.MONOTONIC
    market_type = MarketType.SPOT

    def parse_instruments(
        self,
        payload: Any,
    ) -> InstrumentParseResult:
        body = require_mapping(
            payload,
            field_name="instruments-info",
        )

        result = require_mapping(
            body.get("result", {}),
            field_name="result",
        )

        entries = require_sequence(
            result.get("list", []),
            field_name="list",
        )

        instruments: list[Instrument] = []
        skipped: list[SkippedInstrument] = []

        for entry in entries:
            mapping = require_mapping(
                entry,
                field_name="instrument",
            )

            raw_symbol = str(mapping.get("symbol") or "")

            try:
                instruments.append(
                    self._build_instrument(mapping)
                )
            except (
                CryptoArbitrageError,
                DomainValidationError,
            ) as exc:
                skipped.append(
                    SkippedInstrument(
                        raw_symbol=raw_symbol,
                        reason=str(exc),
                    )
                )

        return InstrumentParseResult(
            instruments=tuple(instruments),
            skipped=tuple(skipped),
        )

    def _build_instrument(
        self,
        mapping: dict[str, Any],
    ) -> Instrument:
        symbol = str(mapping.get("symbol") or "").strip()

        if not symbol:
            raise DomainValidationError(
                "symbol é obrigatório."
            )

        lot_filter = require_mapping(
            mapping.get("lotSizeFilter", {}),
            field_name="lotSizeFilter",
        )

        price_filter = require_mapping(
            mapping.get("priceFilter", {}),
            field_name="priceFilter",
        )

        tick_size = price_filter.get("tickSize")
        base_precision = lot_filter.get("basePrecision")
        min_quantity = lot_filter.get("minOrderQty")
        min_notional = lot_filter.get("minOrderAmt")

        missing = [
            name
            for name, value in (
                ("priceFilter.tickSize", tick_size),
                (
                    "lotSizeFilter.basePrecision",
                    base_precision,
                ),
                ("lotSizeFilter.minOrderQty", min_quantity),
            )
            if value in (None, "")
        ]

        if missing:
            raise DomainValidationError(
                "Campos ausentes: " + ", ".join(missing)
            )

        return Instrument(
            venue_id=self.venue_id,
            instrument_id=symbol.upper(),
            pair=build_pair(
                str(mapping.get("baseCoin") or ""),
                str(mapping.get("quoteCoin") or ""),
            ),
            market_type=self.market_type,
            price_tick=str(tick_size),
            quantity_step=str(base_precision),
            min_quantity=str(min_quantity),
            min_notional=(
                str(min_notional)
                if min_notional not in (None, "")
                else "0"
            ),
            status=STATUS_MAP.get(
                str(mapping.get("status") or "").lower(),
                InstrumentStatus.UNKNOWN,
            ),
        )

    def parse_rest_snapshot(
        self,
        payload: Any,
        *,
        instrument_id: str,
    ) -> SnapshotPayload:
        body = require_mapping(
            payload,
            field_name="orderbook",
        )

        result = require_mapping(
            body.get("result", {}),
            field_name="result",
        )

        return SnapshotPayload(
            instrument_id=str(instrument_id).strip().upper(),
            bids=parse_levels(
                result.get("b", []),
                field_name="b",
            ),
            asks=parse_levels(
                result.get("a", []),
                field_name="a",
            ),
            update_id=coerce_int(
                result.get("u"),
                field_name="u",
            ),
            exchange_timestamp=milliseconds_to_datetime(
                result.get("ts"),
                field_name="ts",
            ),
        )

    def parse_stream_message(
        self,
        payload: Any,
    ) -> StreamMessage:
        body = require_mapping(
            payload,
            field_name="mensagem",
        )

        if body.get("op") or body.get("success") is not None:
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail="Resposta de controle do WebSocket.",
            )

        message_type = str(
            body.get("type") or ""
        ).strip().lower()

        if message_type not in ("snapshot", "delta"):
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail=(
                    "Tipo não tratado: "
                    f"{message_type or 'ausente'}."
                ),
            )

        data = require_mapping(
            body.get("data", {}),
            field_name="data",
        )

        instrument_id = str(
            data.get("s") or ""
        ).strip().upper()

        bids = parse_levels(
            data.get("b", []),
            field_name="b",
        )

        asks = parse_levels(
            data.get("a", []),
            field_name="a",
        )

        update_id = coerce_int(
            data.get("u"),
            field_name="u",
        )

        exchange_timestamp = milliseconds_to_datetime(
            body.get("ts"),
            field_name="ts",
        )

        is_service_restart = (
            update_id == SERVICE_RESTART_UPDATE_ID
        )

        if message_type == "snapshot" or is_service_restart:
            return StreamMessage(
                kind=StreamMessageKind.SNAPSHOT,
                instrument_id=instrument_id,
                snapshot=SnapshotPayload(
                    instrument_id=instrument_id,
                    bids=bids,
                    asks=asks,
                    update_id=update_id,
                    exchange_timestamp=exchange_timestamp,
                ),
                detail=(
                    "u=1 indica reinício de serviço; o livro "
                    "local deve ser sobrescrito."
                    if is_service_restart
                    and message_type == "delta"
                    else None
                ),
            )

        return StreamMessage(
            kind=StreamMessageKind.DELTA,
            instrument_id=instrument_id,
            update=BookUpdate(
                bids=bids,
                asks=asks,
                final_update_id=update_id,
                exchange_timestamp=exchange_timestamp,
            ),
        )
