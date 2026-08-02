"""Fase 19A - politica de frescor e rastreio de latencia."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    PrecisionError,
    StaleMarketDataError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookLevel,
    OrderBookSnapshot,
)
from app.crypto_arbitrage.market_data.freshness import (
    FreshnessPolicy,
    is_usable_for_pricing,
    milliseconds_between,
)
from app.crypto_arbitrage.market_data.latency import (
    LatencyTracker,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)


def _snapshot(received: datetime) -> OrderBookSnapshot:
    return OrderBookSnapshot(
        venue_id="BINANCE",
        instrument_id="BTCUSDT",
        bids=(
            OrderBookLevel(
                price=Decimal("100"),
                quantity=Decimal("1"),
            ),
        ),
        asks=(
            OrderBookLevel(
                price=Decimal("101"),
                quantity=Decimal("1"),
            ),
        ),
        exchange_timestamp=received,
        received_timestamp=received,
    )


def test_policy_accepts_recent_book():
    policy = FreshnessPolicy.create(max_age_ms=1000)

    verdict = policy.evaluate(
        _snapshot(MOMENT),
        MOMENT + timedelta(milliseconds=200),
    )

    assert verdict.is_fresh is True
    assert verdict.age_ms == Decimal("200")


def test_policy_rejects_stale_book():
    policy = FreshnessPolicy.create(max_age_ms=1000)

    verdict = policy.evaluate(
        _snapshot(MOMENT),
        MOMENT + timedelta(milliseconds=1500),
    )

    assert verdict.is_fresh is False
    assert "excede o limite" in verdict.reason


def test_policy_rejects_clock_skew_beyond_tolerance():
    policy = FreshnessPolicy.create(
        max_age_ms=1000,
        max_clock_skew_ms=100,
    )

    verdict = policy.evaluate(
        _snapshot(MOMENT),
        MOMENT - timedelta(milliseconds=500),
    )

    assert verdict.is_fresh is False
    assert "futuro" in verdict.reason


def test_policy_tolerates_small_clock_skew():
    policy = FreshnessPolicy.create(
        max_age_ms=1000,
        max_clock_skew_ms=500,
    )

    verdict = policy.evaluate(
        _snapshot(MOMENT),
        MOMENT - timedelta(milliseconds=100),
    )

    assert verdict.is_fresh is True


def test_require_fresh_raises_for_stale():
    policy = FreshnessPolicy.create(max_age_ms=100)

    with pytest.raises(StaleMarketDataError):
        policy.require_fresh(
            _snapshot(MOMENT),
            MOMENT + timedelta(seconds=5),
        )


def test_policy_requires_positive_limits():
    with pytest.raises(DomainValidationError):
        FreshnessPolicy.create(max_age_ms=0)


def test_policy_requires_aware_now():
    policy = FreshnessPolicy.create()

    with pytest.raises(DomainValidationError):
        policy.evaluate(
            _snapshot(MOMENT),
            datetime(2026, 8, 2),
        )


def test_degraded_connector_blocks_even_with_fresh_book():
    policy = FreshnessPolicy.create(max_age_ms=1000)

    verdict = is_usable_for_pricing(
        _snapshot(MOMENT),
        ConnectorState.DEGRADED,
        policy,
        MOMENT + timedelta(milliseconds=10),
    )

    assert verdict.is_fresh is False
    assert "DEGRADED" in verdict.reason


def test_ready_connector_with_fresh_book_is_usable():
    policy = FreshnessPolicy.create(max_age_ms=1000)

    verdict = is_usable_for_pricing(
        _snapshot(MOMENT),
        ConnectorState.READY,
        policy,
        MOMENT + timedelta(milliseconds=10),
    )

    assert verdict.is_fresh is True


def test_milliseconds_between_requires_timezone():
    with pytest.raises(DomainValidationError):
        milliseconds_between(
            datetime(2026, 8, 2),
            MOMENT,
        )


def test_milliseconds_between_computes_delta():
    assert milliseconds_between(
        MOMENT,
        MOMENT + timedelta(milliseconds=250),
    ) == Decimal("250")


def test_tracker_starts_empty():
    tracker = LatencyTracker()

    assert tracker.count == 0
    assert tracker.last is None
    assert tracker.average is None
    assert tracker.percentile("0.95") is None


def test_tracker_records_samples():
    tracker = LatencyTracker()

    for value in ("10", "20", "30"):
        tracker.record(value)

    assert tracker.count == 3
    assert tracker.last == Decimal("30")
    assert tracker.minimum == Decimal("10")
    assert tracker.maximum == Decimal("30")
    assert tracker.average == Decimal("20")


def test_tracker_rejects_float():
    tracker = LatencyTracker()

    with pytest.raises(PrecisionError):
        tracker.record(1.5)


def test_tracker_preserves_negative_clock_skew():
    tracker = LatencyTracker()

    tracker.record("-40")

    assert tracker.last == Decimal("-40")
    assert tracker.minimum == Decimal("-40")


def test_tracker_window_discards_oldest():
    tracker = LatencyTracker(window=3)

    for value in ("1", "2", "3", "4"):
        tracker.record(value)

    assert tracker.count == 3
    assert tracker.total_observed == 4
    assert tracker.minimum == Decimal("2")


def test_tracker_percentile_uses_position():
    tracker = LatencyTracker()

    for value in ("1", "2", "3", "4", "5"):
        tracker.record(value)

    assert tracker.percentile("1") == Decimal("5")
    assert tracker.percentile("0.2") == Decimal("1")


def test_tracker_percentile_validates_ratio():
    tracker = LatencyTracker()
    tracker.record("1")

    with pytest.raises(DomainValidationError):
        tracker.percentile("0")

    with pytest.raises(DomainValidationError):
        tracker.percentile("1.5")


def test_tracker_requires_positive_window():
    with pytest.raises(DomainValidationError):
        LatencyTracker(window=0)


def test_tracker_payload_is_serializable():
    tracker = LatencyTracker(label="exchange_to_receive")

    tracker.record("12")

    payload = tracker.to_dict()

    assert payload["label"] == "exchange_to_receive"
    assert payload["count"] == 1
    assert payload["last_ms"] == "12"
    assert payload["p95_ms"] == "12"


def test_tracker_reset_clears_window_not_total():
    tracker = LatencyTracker()

    tracker.record("5")
    tracker.reset()

    assert tracker.count == 0
    assert tracker.total_observed == 1
