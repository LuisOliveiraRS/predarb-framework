"""Tradução dos formatos públicos da OKX V5 Spot.

Formatos confirmados na documentação oficial em 02/08/2026:
`/api/v5/public/instruments?instType=SPOT` e o canal WebSocket
`books`.

Mudança relevante e recente: em **23/06/2026 a OKX depreciou o
`checksum`** dos canais `books`, `books-l2-tbt` e
`books50-l2-tbt`. O campo continua presente mas com valor fixo em
`0`, e a documentação diz explicitamente que ele não deve mais
ser usado para verificar integridade. A orientação oficial passou
a ser `seqId`/`prevSeqId`.

Por isso este adaptador ignora `checksum` de propósito, e usa
`SequenceMode.PREVIOUS_MATCH`: o `prevSeqId` da mensagem N deve
bater com o `seqId` da mensagem N-1.

Os níveis da OKX têm quatro elementos por entrada. Só os dois
primeiros — preço e quantidade — interessam ao livro.
"""

from __future__ import annotations

from decimal import Decimal
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
    "live": InstrumentStatus.TRADING,
    "suspend": InstrumentStatus.HALTED,
    "expired": InstrumentStatus.DELISTED,
    "preopen": InstrumentStatus.UNKNOWN,
    "test": InstrumentStatus.UNKNOWN,
}

BOOK_CHANNELS = (
    "books",
    "books5",
    "books50-l2-tbt",
    "books-l2-tbt",
    "bbo-tbt",
)


class OkxSpotAdapter:
    """Adaptador read-only da OKX V5 Spot."""

    venue_id = "OKX"
    sequence_mode = SequenceMode.PREVIOUS_MATCH
    market_type = MarketType.SPOT
    rest_base_url = "https://www.okx.com"

    def instrument_id_for(self, pair: Any) -> str:
        """`BTC/USDT` vira `BTC-USDT` na OKX."""

        return (
            f"{pair.base_asset}-{pair.quote_asset}"
        ).upper()

    def depth_request(
        self,
        instrument_id: str,
        depth: int,
    ) -> tuple[str, dict[str, Any]]:
        return (
            f"{self.rest_base_url}/api/v5/market/books",
            {
                "instId": str(instrument_id).upper(),
                "sz": str(int(depth)),
            },
        )

    def parse_instruments(
        self,
        payload: Any,
    ) -> InstrumentParseResult:
        body = require_mapping(
            payload,
            field_name="instruments",
        )

        entries = require_sequence(
            body.get("data", []),
            field_name="data",
        )

        instruments: list[Instrument] = []
        skipped: list[SkippedInstrument] = []

        for entry in entries:
            mapping = require_mapping(
                entry,
                field_name="instrument",
            )

            raw_symbol = str(mapping.get("instId") or "")

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
        instrument_id = str(
            mapping.get("instId") or ""
        ).strip()

        if not instrument_id:
            raise DomainValidationError(
                "instId é obrigatório."
            )

        tick_size = mapping.get("tickSz")
        lot_size = mapping.get("lotSz")
        min_size = mapping.get("minSz")

        missing = [
            name
            for name, value in (
                ("tickSz", tick_size),
                ("lotSz", lot_size),
                ("minSz", min_size),
            )
            if value in (None, "")
        ]

        if missing:
            raise DomainValidationError(
                "Campos ausentes: " + ", ".join(missing)
            )

        return Instrument(
            venue_id=self.venue_id,
            instrument_id=instrument_id.upper(),
            pair=build_pair(
                str(mapping.get("baseCcy") or ""),
                str(mapping.get("quoteCcy") or ""),
            ),
            market_type=self.market_type,
            price_tick=str(tick_size),
            quantity_step=str(lot_size),
            min_quantity=str(min_size),
            # A OKX não publica notional mínimo para spot.
            # Zero significa "sem restrição conhecida", nunca
            # "restrição inexistente".
            min_notional=Decimal("0"),
            status=STATUS_MAP.get(
                str(mapping.get("state") or "").lower(),
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
            field_name="books",
        )

        entries = require_sequence(
            body.get("data", []),
            field_name="data",
        )

        if not entries:
            raise DomainValidationError(
                "Resposta de book sem data."
            )

        first = require_mapping(
            entries[0],
            field_name="data[0]",
        )

        return SnapshotPayload(
            instrument_id=str(instrument_id).strip().upper(),
            bids=parse_levels(
                first.get("bids", []),
                field_name="bids",
            ),
            asks=parse_levels(
                first.get("asks", []),
                field_name="asks",
            ),
            update_id=coerce_int(
                first.get("seqId"),
                field_name="seqId",
            ),
            exchange_timestamp=milliseconds_to_datetime(
                first.get("ts"),
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

        if "event" in body:
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail=(
                    "Evento de controle: "
                    f"{body.get('event')}."
                ),
            )

        action = str(body.get("action") or "").strip()

        if not action:
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail="Mensagem sem action.",
            )

        arg = require_mapping(
            body.get("arg", {}),
            field_name="arg",
        )

        channel = str(arg.get("channel") or "").strip()

        if channel and channel not in BOOK_CHANNELS:
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail=f"Canal não tratado: {channel}.",
            )

        instrument_id = str(
            arg.get("instId") or ""
        ).strip().upper()

        entries = require_sequence(
            body.get("data", []),
            field_name="data",
        )

        if not entries:
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                instrument_id=instrument_id or None,
                detail="Mensagem de book sem data.",
            )

        first = require_mapping(
            entries[0],
            field_name="data[0]",
        )

        bids = parse_levels(
            first.get("bids", []),
            field_name="bids",
        )

        asks = parse_levels(
            first.get("asks", []),
            field_name="asks",
        )

        exchange_timestamp = milliseconds_to_datetime(
            first.get("ts"),
            field_name="ts",
        )

        sequence_id = coerce_int(
            first.get("seqId"),
            field_name="seqId",
        )

        if action == "snapshot":
            return StreamMessage(
                kind=StreamMessageKind.SNAPSHOT,
                instrument_id=instrument_id,
                snapshot=SnapshotPayload(
                    instrument_id=instrument_id,
                    bids=bids,
                    asks=asks,
                    update_id=sequence_id,
                    exchange_timestamp=exchange_timestamp,
                ),
            )

        if action != "update":
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                instrument_id=instrument_id,
                detail=f"Action não tratada: {action}.",
            )

        return StreamMessage(
            kind=StreamMessageKind.DELTA,
            instrument_id=instrument_id,
            update=BookUpdate(
                bids=bids,
                asks=asks,
                final_update_id=sequence_id,
                previous_update_id=coerce_int(
                    first.get("prevSeqId"),
                    field_name="prevSeqId",
                ),
                exchange_timestamp=exchange_timestamp,
            ),
        )
