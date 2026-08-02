"""Tradução dos formatos públicos da Binance Spot.

Formatos confirmados na documentação oficial em 02/08/2026:
`/api/v3/exchangeInfo`, `/api/v3/depth` e o stream
`<symbol>@depth`.

A Binance publica `U` (primeiro update id do evento) e `u`
(último). O procedimento documentado é: bufferizar o stream,
buscar o snapshot REST com `lastUpdateId`, descartar eventos com
`u <= lastUpdateId`, exigir que o primeiro evento aplicado
satisfaça `U <= lastUpdateId + 1 <= u`, e depois que cada evento
tenha `U` igual ao `u` anterior mais um.

Isso corresponde exatamente a `SequenceMode.RANGE`, que cobre as
duas fases com uma regra só.

Cuidado documentado: o campo `pu` existe na API de **futuros**
USDS-M, não no spot. Validar contra ele aqui compararia com um
campo inexistente.
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
    "TRADING": InstrumentStatus.TRADING,
    "HALT": InstrumentStatus.HALTED,
    "BREAK": InstrumentStatus.HALTED,
}


def _filter_value(
    filters: Any,
    filter_type: str,
    key: str,
) -> str | None:
    for entry in require_sequence(
        filters,
        field_name="filters",
    ):
        mapping = require_mapping(
            entry,
            field_name="filter",
        )

        if mapping.get("filterType") == filter_type:
            value = mapping.get(key)

            return None if value is None else str(value)

    return None


class BinanceSpotAdapter:
    """Adaptador read-only da Binance Spot."""

    venue_id = "BINANCE"
    sequence_mode = SequenceMode.RANGE
    market_type = MarketType.SPOT
    rest_base_url = "https://api.binance.com"

    def instrument_id_for(self, pair: Any) -> str:
        """`BTC/USDT` vira `BTCUSDT` na Binance."""

        return (
            f"{pair.base_asset}{pair.quote_asset}"
        ).upper()

    def depth_request(
        self,
        instrument_id: str,
        depth: int,
    ) -> tuple[str, dict[str, Any]]:
        return (
            f"{self.rest_base_url}/api/v3/depth",
            {
                "symbol": str(instrument_id).upper(),
                "limit": int(depth),
            },
        )

    def parse_instruments(
        self,
        payload: Any,
    ) -> InstrumentParseResult:
        body = require_mapping(
            payload,
            field_name="exchangeInfo",
        )

        symbols = require_sequence(
            body.get("symbols", []),
            field_name="symbols",
        )

        instruments: list[Instrument] = []
        skipped: list[SkippedInstrument] = []

        for entry in symbols:
            mapping = require_mapping(
                entry,
                field_name="symbol",
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

        filters = mapping.get("filters", [])

        tick_size = _filter_value(
            filters,
            "PRICE_FILTER",
            "tickSize",
        )

        step_size = _filter_value(
            filters,
            "LOT_SIZE",
            "stepSize",
        )

        min_quantity = _filter_value(
            filters,
            "LOT_SIZE",
            "minQty",
        )

        min_notional = _filter_value(
            filters,
            "NOTIONAL",
            "minNotional",
        ) or _filter_value(
            filters,
            "MIN_NOTIONAL",
            "minNotional",
        )

        missing = [
            name
            for name, value in (
                ("PRICE_FILTER.tickSize", tick_size),
                ("LOT_SIZE.stepSize", step_size),
                ("LOT_SIZE.minQty", min_quantity),
            )
            if value is None
        ]

        if missing:
            raise DomainValidationError(
                "Filtros ausentes: " + ", ".join(missing)
            )

        return Instrument(
            venue_id=self.venue_id,
            instrument_id=symbol.upper(),
            pair=build_pair(
                str(mapping.get("baseAsset") or ""),
                str(mapping.get("quoteAsset") or ""),
            ),
            market_type=self.market_type,
            price_tick=str(tick_size),
            quantity_step=str(step_size),
            min_quantity=str(min_quantity),
            min_notional=(
                str(min_notional)
                if min_notional is not None
                else Decimal("0")
            ),
            status=STATUS_MAP.get(
                str(mapping.get("status") or "").upper(),
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
            field_name="depth",
        )

        return SnapshotPayload(
            instrument_id=str(instrument_id).strip().upper(),
            bids=parse_levels(
                body.get("bids", []),
                field_name="bids",
            ),
            asks=parse_levels(
                body.get("asks", []),
                field_name="asks",
            ),
            update_id=coerce_int(
                body.get("lastUpdateId"),
                field_name="lastUpdateId",
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

        # Streams combinados envelopam o evento em "data".
        if "data" in body and "e" not in body:
            body = require_mapping(
                body["data"],
                field_name="data",
            )

        event = str(body.get("e") or "").strip()

        if event != "depthUpdate":
            return StreamMessage(
                kind=StreamMessageKind.IGNORED,
                detail=(
                    f"Evento não tratado: {event or 'sem e'}."
                ),
            )

        first = coerce_int(
            body.get("U"),
            field_name="U",
        )

        final = coerce_int(
            body.get("u"),
            field_name="u",
        )

        if first is None or final is None:
            raise DomainValidationError(
                "depthUpdate exige U e u."
            )

        instrument_id = str(
            body.get("s") or ""
        ).strip().upper()

        return StreamMessage(
            kind=StreamMessageKind.DELTA,
            instrument_id=instrument_id,
            update=BookUpdate(
                bids=parse_levels(
                    body.get("b", []),
                    field_name="b",
                ),
                asks=parse_levels(
                    body.get("a", []),
                    field_name="a",
                ),
                first_update_id=first,
                final_update_id=final,
                exchange_timestamp=(
                    milliseconds_to_datetime(
                        body.get("E"),
                        field_name="E",
                    )
                ),
            ),
        )

    def is_snapshot_usable(
        self,
        snapshot: SnapshotPayload,
        first_buffered_update_id: int | None,
    ) -> bool:
        """Implementa o passo 4 do procedimento da Binance.

        Se o `lastUpdateId` do snapshot for menor que o `U` do
        primeiro evento bufferizado, o snapshot é velho demais
        para conectar com o stream e outro precisa ser buscado.
        """

        if first_buffered_update_id is None:
            return True

        if snapshot.update_id is None:
            return False

        return (
            snapshot.update_id >= first_buffered_update_id
        )
