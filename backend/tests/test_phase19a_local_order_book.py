"""Fase 19A - book local, sequencia, gap e resync."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.domain.enums import ConnectorState, Side
from app.crypto_arbitrage.domain.errors import (
    BookNotReadyError,
    CorruptedBookError,
    DomainValidationError,
    SequenceGapError,
)
from app.crypto_arbitrage.market_data.local_book import (
    BookLevelChange,
    BookUpdate,
    LocalOrderBook,
    SequenceMode,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)


def _change(price: str, quantity: str) -> BookLevelChange:
    return BookLevelChange(
        price=Decimal(price),
        quantity=Decimal(quantity),
    )


def _book(
    mode: SequenceMode = SequenceMode.STRICT_INCREMENT,
) -> LocalOrderBook:
    book = LocalOrderBook(
        "binance",
        "btcusdt",
        sequence_mode=mode,
    )

    book.apply_snapshot(
        bids=[_change("100", "1"), _change("99", "2")],
        asks=[_change("101", "1"), _change("102", "2")],
        update_id=10,
        exchange_timestamp=MOMENT,
        received_timestamp=MOMENT,
    )

    return book


def test_book_normalizes_identifiers():
    book = LocalOrderBook("binance", "btcusdt")

    assert book.venue_id == "BINANCE"
    assert book.instrument_id == "BTCUSDT"


def test_book_requires_identifiers():
    with pytest.raises(DomainValidationError):
        LocalOrderBook("", "BTCUSDT")


def test_new_book_is_not_ready():
    book = LocalOrderBook("BINANCE", "BTCUSDT")

    assert book.is_ready is False
    assert book.state is ConnectorState.CONNECTING


def test_delta_before_snapshot_is_refused():
    book = LocalOrderBook("BINANCE", "BTCUSDT")

    with pytest.raises(BookNotReadyError):
        book.apply_update(
            BookUpdate(
                bids=(_change("100", "1"),),
                final_update_id=1,
            )
        )


def test_snapshot_makes_book_ready():
    book = _book()

    assert book.is_ready is True
    assert book.state is ConnectorState.READY
    assert book.best_bid() == Decimal("100")
    assert book.best_ask() == Decimal("101")
    assert book.depth() == (2, 2)


def test_update_applies_and_advances_sequence():
    book = _book()

    applied = book.apply_update(
        BookUpdate(
            bids=(_change("100", "5"),),
            final_update_id=11,
        )
    )

    assert applied is True
    assert book.stats.last_update_id == 11
    assert book.stats.applied_updates == 1


def test_zero_quantity_removes_level():
    book = _book()

    book.apply_update(
        BookUpdate(
            bids=(_change("99", "0"),),
            final_update_id=11,
        )
    )

    assert book.depth() == (1, 2)


def test_old_update_is_ignored_not_rejected():
    book = _book()

    applied = book.apply_update(
        BookUpdate(
            bids=(_change("100", "9"),),
            final_update_id=5,
        )
    )

    assert applied is False
    assert book.stats.ignored_stale_updates == 1
    assert book.is_ready is True


def test_strict_increment_detects_gap():
    book = _book()

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(
                bids=(_change("100", "5"),),
                final_update_id=13,
            )
        )

    assert book.needs_resync is True
    assert book.stats.gap_count == 1
    assert book.state is ConnectorState.DEGRADED


def test_book_awaiting_resync_refuses_updates():
    book = _book()

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(final_update_id=13)
        )

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(final_update_id=11)
        )


def test_resync_snapshot_restores_book():
    book = _book()

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(final_update_id=99)
        )

    book.apply_snapshot(
        bids=[_change("200", "1")],
        asks=[_change("201", "1")],
        update_id=99,
        received_timestamp=MOMENT,
    )

    assert book.is_ready is True
    assert book.needs_resync is False
    assert book.stats.resync_count == 1
    assert book.best_bid() == Decimal("200")


def test_range_mode_accepts_covering_interval():
    book = _book(SequenceMode.RANGE)

    applied = book.apply_update(
        BookUpdate(
            bids=(_change("100", "3"),),
            first_update_id=8,
            final_update_id=15,
        )
    )

    assert applied is True
    assert book.stats.last_update_id == 15


def test_range_mode_detects_hole():
    book = _book(SequenceMode.RANGE)

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(
                first_update_id=13,
                final_update_id=20,
            )
        )

    assert book.needs_resync is True


def test_range_mode_requires_first_update_id():
    book = _book(SequenceMode.RANGE)

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(final_update_id=20)
        )


def test_previous_match_mode_accepts_chained_update():
    book = _book(SequenceMode.PREVIOUS_MATCH)

    applied = book.apply_update(
        BookUpdate(
            bids=(_change("100", "4"),),
            previous_update_id=10,
            final_update_id=11,
        )
    )

    assert applied is True
    assert book.stats.last_update_id == 11


def test_previous_match_mode_detects_broken_chain():
    book = _book(SequenceMode.PREVIOUS_MATCH)

    with pytest.raises(SequenceGapError):
        book.apply_update(
            BookUpdate(
                previous_update_id=12,
                final_update_id=13,
            )
        )


def test_previous_match_ignores_replayed_update():
    book = _book(SequenceMode.PREVIOUS_MATCH)

    applied = book.apply_update(
        BookUpdate(
            previous_update_id=4,
            final_update_id=5,
        )
    )

    assert applied is False


def test_none_mode_accepts_anything():
    book = _book(SequenceMode.NONE)

    assert book.apply_update(
        BookUpdate(bids=(_change("100", "7"),))
    ) is True


def test_crossed_book_raises_and_requires_resync():
    book = _book()

    with pytest.raises(CorruptedBookError):
        book.apply_update(
            BookUpdate(
                bids=(_change("105", "1"),),
                final_update_id=11,
            )
        )

    assert book.needs_resync is True


def test_mark_for_resync_records_reason():
    book = _book()

    book.mark_for_resync("websocket reconectado")

    assert book.needs_resync is True
    assert book.is_ready is False
    assert book.state is ConnectorState.DEGRADED
    assert (
        book.status()["resync_reason"]
        == "websocket reconectado"
    )


def test_snapshot_export_requires_ready_book():
    book = LocalOrderBook("BINANCE", "BTCUSDT")

    with pytest.raises(BookNotReadyError):
        book.to_snapshot(received_timestamp=MOMENT)


def test_snapshot_export_blocked_while_awaiting_resync():
    book = _book()
    book.mark_for_resync("teste")

    with pytest.raises(BookNotReadyError):
        book.to_snapshot(received_timestamp=MOMENT)


def test_snapshot_export_produces_domain_model():
    book = _book()

    snapshot = book.to_snapshot(
        received_timestamp=MOMENT + timedelta(
            milliseconds=30
        )
    )

    assert snapshot.venue_id == "BINANCE"
    assert snapshot.instrument_id == "BTCUSDT"
    assert snapshot.best_bid.price == Decimal("100")
    assert snapshot.best_ask.price == Decimal("101")
    assert snapshot.sequence == 10
    assert snapshot.is_snapshot is False

    result = snapshot.vwap_for_quantity(
        Side.BUY,
        Decimal("1"),
    )

    assert result.vwap == Decimal("101")


def test_snapshot_export_respects_depth_limit():
    book = _book()

    snapshot = book.to_snapshot(
        received_timestamp=MOMENT,
        depth=1,
    )

    assert len(snapshot.bids) == 1
    assert len(snapshot.asks) == 1


def test_snapshot_export_orders_levels_correctly():
    book = LocalOrderBook("BINANCE", "BTCUSDT")

    book.apply_snapshot(
        bids=[
            _change("98", "1"),
            _change("100", "1"),
            _change("99", "1"),
        ],
        asks=[
            _change("103", "1"),
            _change("101", "1"),
            _change("102", "1"),
        ],
        update_id=1,
        received_timestamp=MOMENT,
    )

    snapshot = book.to_snapshot(
        received_timestamp=MOMENT
    )

    assert [
        level.price for level in snapshot.bids
    ] == [Decimal("100"), Decimal("99"), Decimal("98")]

    assert [
        level.price for level in snapshot.asks
    ] == [Decimal("101"), Decimal("102"), Decimal("103")]


def test_status_reports_observable_counters():
    book = _book()

    book.apply_update(
        BookUpdate(final_update_id=11)
    )

    status = book.status()

    assert status["venue_id"] == "BINANCE"
    assert status["state"] == ConnectorState.READY.value
    assert status["is_ready"] is True
    assert status["stats"]["applied_updates"] == 1
    assert status["stats"]["last_update_id"] == 11
