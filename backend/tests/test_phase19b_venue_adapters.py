"""Fase 19B - adaptadores Binance, OKX e Bybit.

Fixtures nos formatos confirmados na documentacao oficial em
02/08/2026. Nenhum teste toca a rede.
"""

from datetime import datetime, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.connectors.binance import (
    BinanceSpotAdapter,
)
from app.crypto_arbitrage.connectors.bybit import (
    BybitSpotAdapter,
)
from app.crypto_arbitrage.connectors.okx import (
    OkxSpotAdapter,
)
from app.crypto_arbitrage.connectors.registry import (
    ConnectorRegistry,
    assert_no_execution_capability,
)
from app.crypto_arbitrage.connectors.venue_adapter import (
    StreamMessageKind,
    VenueAdapter,
    parse_levels,
)
from app.crypto_arbitrage.domain.enums import (
    InstrumentStatus,
    Side,
)
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    SequenceGapError,
)
from app.crypto_arbitrage.market_data.local_book import (
    LocalOrderBook,
    SequenceMode,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)

ADAPTERS = (
    BinanceSpotAdapter(),
    OkxSpotAdapter(),
    BybitSpotAdapter(),
)


# ---------------------------------------------------------------
# Helpers compartilhados
# ---------------------------------------------------------------


def test_parse_levels_ignores_extra_elements():
    levels = parse_levels(
        [["100.5", "2", "0", "3"]],
        field_name="bids",
    )

    assert levels[0].price == Decimal("100.5")
    assert levels[0].quantity == Decimal("2")


def test_parse_levels_accepts_zero_quantity_as_removal():
    levels = parse_levels(
        [["100", "0"]],
        field_name="bids",
    )

    assert levels[0].is_removal is True


def test_parse_levels_rejects_short_rows():
    with pytest.raises(DomainValidationError):
        parse_levels([["100"]], field_name="bids")


def test_parse_levels_rejects_non_list():
    with pytest.raises(DomainValidationError):
        parse_levels("100", field_name="bids")


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_adapters_satisfy_protocol(adapter):
    assert isinstance(adapter, VenueAdapter)


@pytest.mark.parametrize("adapter", ADAPTERS)
def test_adapters_have_no_execution_capability(adapter):
    assert_no_execution_capability(adapter)


def test_each_venue_declares_its_sequence_mode():
    assert (
        BinanceSpotAdapter.sequence_mode
        is SequenceMode.RANGE
    )
    assert (
        OkxSpotAdapter.sequence_mode
        is SequenceMode.PREVIOUS_MATCH
    )
    assert (
        BybitSpotAdapter.sequence_mode
        is SequenceMode.MONOTONIC
    )


def test_adapters_can_be_registered_as_read_only():
    registry = ConnectorRegistry()

    for adapter in ADAPTERS:
        registry.register_public(adapter)

    assert registry.public_venues() == [
        "BINANCE",
        "BYBIT",
        "OKX",
    ]


# ---------------------------------------------------------------
# Binance
# ---------------------------------------------------------------


BINANCE_EXCHANGE_INFO = {
    "symbols": [
        {
            "symbol": "BTCUSDT",
            "status": "TRADING",
            "baseAsset": "BTC",
            "quoteAsset": "USDT",
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "tickSize": "0.01000000",
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00001000",
                    "stepSize": "0.00001000",
                },
                {
                    "filterType": "NOTIONAL",
                    "minNotional": "5.00000000",
                },
            ],
        },
        {
            "symbol": "ETHUSDT",
            "status": "BREAK",
            "baseAsset": "ETH",
            "quoteAsset": "USDT",
            "filters": [
                {
                    "filterType": "PRICE_FILTER",
                    "tickSize": "0.01000000",
                },
                {
                    "filterType": "LOT_SIZE",
                    "minQty": "0.00010000",
                    "stepSize": "0.00010000",
                },
            ],
        },
        {
            "symbol": "BADUSDT",
            "status": "TRADING",
            "baseAsset": "BAD",
            "quoteAsset": "USDT",
            "filters": [],
        },
    ]
}


def test_binance_parses_instruments():
    result = BinanceSpotAdapter().parse_instruments(
        BINANCE_EXCHANGE_INFO
    )

    assert len(result.instruments) == 2

    btc = result.instruments[0]

    assert btc.venue_id == "BINANCE"
    assert btc.instrument_id == "BTCUSDT"
    assert btc.pair.canonical == "BTC/USDT"
    assert btc.price_tick == Decimal("0.01000000")
    assert btc.min_notional == Decimal("5")
    assert btc.status is InstrumentStatus.TRADING
    assert btc.is_tradable is True


def test_binance_maps_break_status_to_halted():
    result = BinanceSpotAdapter().parse_instruments(
        BINANCE_EXCHANGE_INFO
    )

    eth = result.instruments[1]

    assert eth.status is InstrumentStatus.HALTED
    assert eth.is_tradable is False


def test_binance_records_skipped_symbol_with_reason():
    result = BinanceSpotAdapter().parse_instruments(
        BINANCE_EXCHANGE_INFO
    )

    assert len(result.skipped) == 1
    assert result.skipped[0].raw_symbol == "BADUSDT"
    assert "PRICE_FILTER" in result.skipped[0].reason


def test_binance_parses_rest_snapshot():
    snapshot = BinanceSpotAdapter().parse_rest_snapshot(
        {
            "lastUpdateId": 1027024,
            "bids": [["4.00000000", "431.00000000"]],
            "asks": [["4.00000200", "12.00000000"]],
        },
        instrument_id="btcusdt",
    )

    assert snapshot.instrument_id == "BTCUSDT"
    assert snapshot.update_id == 1027024
    assert snapshot.bids[0].price == Decimal("4")


def test_binance_parses_depth_update():
    message = BinanceSpotAdapter().parse_stream_message(
        {
            "e": "depthUpdate",
            "E": 1785628800000,
            "s": "BTCUSDT",
            "U": 157,
            "u": 160,
            "b": [["0.0024", "10"]],
            "a": [["0.0026", "100"]],
        }
    )

    assert message.kind is StreamMessageKind.DELTA
    assert message.instrument_id == "BTCUSDT"
    assert message.update.first_update_id == 157
    assert message.update.final_update_id == 160
    assert message.update.exchange_timestamp == MOMENT


def test_binance_unwraps_combined_stream_envelope():
    message = BinanceSpotAdapter().parse_stream_message(
        {
            "stream": "btcusdt@depth",
            "data": {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "U": 1,
                "u": 2,
                "b": [],
                "a": [],
            },
        }
    )

    assert message.kind is StreamMessageKind.DELTA


def test_binance_ignores_unrelated_event():
    message = BinanceSpotAdapter().parse_stream_message(
        {"result": None, "id": 1}
    )

    assert message.kind is StreamMessageKind.IGNORED


def test_binance_requires_both_update_ids():
    with pytest.raises(DomainValidationError):
        BinanceSpotAdapter().parse_stream_message(
            {
                "e": "depthUpdate",
                "s": "BTCUSDT",
                "u": 160,
                "b": [],
                "a": [],
            }
        )


def test_binance_snapshot_usability_follows_documented_step():
    adapter = BinanceSpotAdapter()

    stale = adapter.parse_rest_snapshot(
        {"lastUpdateId": 100, "bids": [], "asks": []},
        instrument_id="BTCUSDT",
    )

    assert adapter.is_snapshot_usable(stale, 150) is False
    assert adapter.is_snapshot_usable(stale, 90) is True
    assert adapter.is_snapshot_usable(stale, None) is True


def test_binance_range_mode_works_end_to_end():
    adapter = BinanceSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    snapshot = adapter.parse_rest_snapshot(
        {
            "lastUpdateId": 100,
            "bids": [["99", "1"]],
            "asks": [["101", "1"]],
        },
        instrument_id="BTCUSDT",
    )

    book.apply_snapshot(
        bids=snapshot.bids,
        asks=snapshot.asks,
        update_id=snapshot.update_id,
        received_timestamp=MOMENT,
    )

    # Primeiro evento: U <= lastUpdateId + 1 <= u.
    first = adapter.parse_stream_message(
        {
            "e": "depthUpdate",
            "s": "BTCUSDT",
            "U": 99,
            "u": 105,
            "b": [["99", "3"]],
            "a": [],
        }
    )

    assert book.apply_update(first.update) is True

    # Evento seguinte encadeado: U == u anterior + 1.
    second = adapter.parse_stream_message(
        {
            "e": "depthUpdate",
            "s": "BTCUSDT",
            "U": 106,
            "u": 110,
            "b": [["98", "2"]],
            "a": [],
        }
    )

    assert book.apply_update(second.update) is True
    assert book.stats.last_update_id == 110

    # Buraco na sequencia.
    third = adapter.parse_stream_message(
        {
            "e": "depthUpdate",
            "s": "BTCUSDT",
            "U": 120,
            "u": 130,
            "b": [],
            "a": [],
        }
    )

    with pytest.raises(SequenceGapError):
        book.apply_update(third.update)

    assert book.needs_resync is True


# ---------------------------------------------------------------
# OKX
# ---------------------------------------------------------------


OKX_INSTRUMENTS = {
    "code": "0",
    "data": [
        {
            "instType": "SPOT",
            "instId": "BTC-USDT",
            "baseCcy": "BTC",
            "quoteCcy": "USDT",
            "tickSz": "0.1",
            "lotSz": "0.00000001",
            "minSz": "0.00001",
            "state": "live",
        },
        {
            "instType": "SPOT",
            "instId": "OLD-USDT",
            "baseCcy": "OLD",
            "quoteCcy": "USDT",
            "tickSz": "0.1",
            "lotSz": "0.1",
            "minSz": "1",
            "state": "expired",
        },
        {
            "instType": "SPOT",
            "instId": "BAD-USDT",
            "baseCcy": "BAD",
            "quoteCcy": "USDT",
            "state": "live",
        },
    ],
}


def test_okx_parses_instruments():
    result = OkxSpotAdapter().parse_instruments(
        OKX_INSTRUMENTS
    )

    assert len(result.instruments) == 2

    btc = result.instruments[0]

    assert btc.instrument_id == "BTC-USDT"
    assert btc.pair.canonical == "BTC/USDT"
    assert btc.price_tick == Decimal("0.1")
    assert btc.status is InstrumentStatus.TRADING


def test_okx_maps_expired_to_delisted():
    result = OkxSpotAdapter().parse_instruments(
        OKX_INSTRUMENTS
    )

    assert (
        result.instruments[1].status
        is InstrumentStatus.DELISTED
    )


def test_okx_records_skipped_instrument():
    result = OkxSpotAdapter().parse_instruments(
        OKX_INSTRUMENTS
    )

    assert len(result.skipped) == 1
    assert result.skipped[0].raw_symbol == "BAD-USDT"
    assert "tickSz" in result.skipped[0].reason


def test_okx_parses_snapshot_action():
    message = OkxSpotAdapter().parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [
                        ["8476.98", "415", "0", "13"]
                    ],
                    "bids": [
                        ["8476.97", "256", "0", "12"]
                    ],
                    "ts": "1785628800000",
                    "checksum": 0,
                    "prevSeqId": -1,
                    "seqId": 123456,
                }
            ],
        }
    )

    assert message.kind is StreamMessageKind.SNAPSHOT
    assert message.instrument_id == "BTC-USDT"
    assert message.snapshot.update_id == 123456
    assert (
        message.snapshot.asks[0].price
        == Decimal("8476.98")
    )
    assert message.snapshot.exchange_timestamp == MOMENT


def test_okx_parses_update_action_with_chain():
    message = OkxSpotAdapter().parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "update",
            "data": [
                {
                    "asks": [["8476.98", "0", "0", "0"]],
                    "bids": [],
                    "ts": "1785628800000",
                    "checksum": 0,
                    "prevSeqId": 123456,
                    "seqId": 123457,
                }
            ],
        }
    )

    assert message.kind is StreamMessageKind.DELTA
    assert message.update.previous_update_id == 123456
    assert message.update.final_update_id == 123457
    assert message.update.asks[0].is_removal is True


def test_okx_ignores_control_event():
    message = OkxSpotAdapter().parse_stream_message(
        {
            "event": "subscribe",
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
        }
    )

    assert message.kind is StreamMessageKind.IGNORED


def test_okx_ignores_unrelated_channel():
    message = OkxSpotAdapter().parse_stream_message(
        {
            "arg": {
                "channel": "trades",
                "instId": "BTC-USDT",
            },
            "action": "update",
            "data": [],
        }
    )

    assert message.kind is StreamMessageKind.IGNORED


def test_okx_previous_match_works_end_to_end():
    adapter = OkxSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        "BTC-USDT",
        sequence_mode=adapter.sequence_mode,
    )

    snapshot_message = adapter.parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "snapshot",
            "data": [
                {
                    "asks": [["101", "1", "0", "1"]],
                    "bids": [["99", "1", "0", "1"]],
                    "ts": "1785628800000",
                    "prevSeqId": -1,
                    "seqId": 10,
                }
            ],
        }
    )

    book.apply_snapshot(
        bids=snapshot_message.snapshot.bids,
        asks=snapshot_message.snapshot.asks,
        update_id=snapshot_message.snapshot.update_id,
        received_timestamp=MOMENT,
    )

    chained = adapter.parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "update",
            "data": [
                {
                    "asks": [],
                    "bids": [["99", "5", "0", "1"]],
                    "ts": "1785628800000",
                    "prevSeqId": 10,
                    "seqId": 11,
                }
            ],
        }
    )

    assert book.apply_update(chained.update) is True

    broken = adapter.parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "update",
            "data": [
                {
                    "asks": [],
                    "bids": [],
                    "ts": "1785628800000",
                    "prevSeqId": 99,
                    "seqId": 100,
                }
            ],
        }
    )

    with pytest.raises(SequenceGapError):
        book.apply_update(broken.update)


def test_okx_checksum_is_ignored_because_deprecated():
    """A OKX fixou checksum em 0 em 23/06/2026."""

    message = OkxSpotAdapter().parse_stream_message(
        {
            "arg": {
                "channel": "books",
                "instId": "BTC-USDT",
            },
            "action": "update",
            "data": [
                {
                    "asks": [],
                    "bids": [["99", "1", "0", "1"]],
                    "ts": "1785628800000",
                    "checksum": 0,
                    "prevSeqId": 1,
                    "seqId": 2,
                }
            ],
        }
    )

    assert message.kind is StreamMessageKind.DELTA


# ---------------------------------------------------------------
# Bybit
# ---------------------------------------------------------------


BYBIT_INSTRUMENTS = {
    "retCode": 0,
    "result": {
        "category": "spot",
        "list": [
            {
                "symbol": "BTCUSDT",
                "baseCoin": "BTC",
                "quoteCoin": "USDT",
                "status": "Trading",
                "lotSizeFilter": {
                    "basePrecision": "0.000001",
                    "minOrderQty": "0.000048",
                    "minOrderAmt": "1",
                },
                "priceFilter": {"tickSize": "0.01"},
            },
            {
                "symbol": "BADUSDT",
                "baseCoin": "BAD",
                "quoteCoin": "USDT",
                "status": "Trading",
                "lotSizeFilter": {},
                "priceFilter": {},
            },
        ],
    },
}


def test_bybit_parses_instruments():
    result = BybitSpotAdapter().parse_instruments(
        BYBIT_INSTRUMENTS
    )

    assert len(result.instruments) == 1

    btc = result.instruments[0]

    assert btc.venue_id == "BYBIT"
    assert btc.instrument_id == "BTCUSDT"
    assert btc.quantity_step == Decimal("0.000001")
    assert btc.min_notional == Decimal("1")
    assert btc.status is InstrumentStatus.TRADING


def test_bybit_records_skipped_instrument():
    result = BybitSpotAdapter().parse_instruments(
        BYBIT_INSTRUMENTS
    )

    assert len(result.skipped) == 1
    assert result.skipped[0].raw_symbol == "BADUSDT"


def test_bybit_parses_snapshot_message():
    message = BybitSpotAdapter().parse_stream_message(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["30247.20", "30.028"]],
                "a": [["30248.70", "0.001"]],
                "u": 177400507,
                "seq": 7961638724,
            },
        }
    )

    assert message.kind is StreamMessageKind.SNAPSHOT
    assert message.snapshot.update_id == 177400507
    assert message.snapshot.exchange_timestamp == MOMENT


def test_bybit_parses_delta_message():
    message = BybitSpotAdapter().parse_stream_message(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["30247.20", "0"]],
                "a": [],
                "u": 177400508,
                "seq": 7961638725,
            },
        }
    )

    assert message.kind is StreamMessageKind.DELTA
    assert message.update.final_update_id == 177400508
    assert message.update.bids[0].is_removal is True


def test_bybit_treats_update_id_one_as_service_restart():
    """u=1 e reinicio de servico, nao delta."""

    message = BybitSpotAdapter().parse_stream_message(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "delta",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["30000", "1"]],
                "a": [["30001", "1"]],
                "u": 1,
                "seq": 1,
            },
        }
    )

    assert message.kind is StreamMessageKind.SNAPSHOT
    assert "reinício de serviço" in message.detail


def test_bybit_ignores_subscription_ack():
    message = BybitSpotAdapter().parse_stream_message(
        {
            "success": True,
            "op": "subscribe",
            "conn_id": "abc",
        }
    )

    assert message.kind is StreamMessageKind.IGNORED


def test_bybit_monotonic_accepts_jump_without_false_gap():
    """A Bybit nao documenta incremento de 1, entao salto nao e gap."""

    adapter = BybitSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=100,
        received_timestamp=MOMENT,
    )

    jumped = adapter.parse_stream_message(
        {
            "type": "delta",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["99", "1"]],
                "a": [],
                "u": 500,
                "seq": 1,
            },
        }
    )

    assert book.apply_update(jumped.update) is True
    assert book.needs_resync is False
    assert book.stats.gap_count == 0


def test_bybit_monotonic_still_ignores_replay():
    adapter = BybitSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=100,
        received_timestamp=MOMENT,
    )

    replay = adapter.parse_stream_message(
        {
            "type": "delta",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["99", "1"]],
                "a": [],
                "u": 50,
                "seq": 1,
            },
        }
    )

    assert book.apply_update(replay.update) is False
    assert book.stats.ignored_stale_updates == 1


def test_bybit_parses_rest_snapshot():
    snapshot = BybitSpotAdapter().parse_rest_snapshot(
        {
            "retCode": 0,
            "result": {
                "s": "BTCUSDT",
                "b": [["30247.20", "30.028"]],
                "a": [["30248.70", "0.001"]],
                "ts": 1785628800000,
                "u": 177400507,
            },
        },
        instrument_id="btcusdt",
    )

    assert snapshot.instrument_id == "BTCUSDT"
    assert snapshot.update_id == 177400507


# ---------------------------------------------------------------
# Integracao entre venues
# ---------------------------------------------------------------


def test_three_venues_produce_comparable_snapshots():
    """Aceitacao da fase: tres books normalizados."""

    books = []

    binance = BinanceSpotAdapter()
    okx = OkxSpotAdapter()
    bybit = BybitSpotAdapter()

    payloads = (
        (
            binance,
            "BTCUSDT",
            binance.parse_rest_snapshot(
                {
                    "lastUpdateId": 1,
                    "bids": [["99.5", "2"]],
                    "asks": [["100.5", "2"]],
                },
                instrument_id="BTCUSDT",
            ),
        ),
        (
            okx,
            "BTC-USDT",
            okx.parse_rest_snapshot(
                {
                    "data": [
                        {
                            "bids": [
                                ["99.4", "2", "0", "1"]
                            ],
                            "asks": [
                                ["100.6", "2", "0", "1"]
                            ],
                            "ts": "1785628800000",
                            "seqId": 1,
                        }
                    ]
                },
                instrument_id="BTC-USDT",
            ),
        ),
        (
            bybit,
            "BTCUSDT",
            bybit.parse_rest_snapshot(
                {
                    "result": {
                        "b": [["99.3", "2"]],
                        "a": [["100.7", "2"]],
                        "ts": 1785628800000,
                        "u": 1,
                    }
                },
                instrument_id="BTCUSDT",
            ),
        ),
    )

    for adapter, instrument_id, payload in payloads:
        book = LocalOrderBook(
            adapter.venue_id,
            instrument_id,
            sequence_mode=adapter.sequence_mode,
        )

        book.apply_snapshot(
            bids=payload.bids,
            asks=payload.asks,
            update_id=payload.update_id,
            received_timestamp=MOMENT,
        )

        books.append(
            book.to_snapshot(received_timestamp=MOMENT)
        )

    assert [book.venue_id for book in books] == [
        "BINANCE",
        "OKX",
        "BYBIT",
    ]

    # Todos precificam a mesma quantidade pela profundidade.
    for book in books:
        result = book.vwap_for_quantity(
            Side.BUY,
            Decimal("1"),
        )

        assert result.vwap > Decimal("100")
