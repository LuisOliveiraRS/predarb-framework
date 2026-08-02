"""Fase 19C1 - backoff, rate limit, metricas e orquestracao."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.connectors.binance import (
    BinanceSpotAdapter,
)
from app.crypto_arbitrage.connectors.bybit import (
    BybitSpotAdapter,
)
from app.crypto_arbitrage.connectors.transport import (
    RestTransport,
    WebSocketTransport,
)
from app.crypto_arbitrage.domain.enums import ConnectorState
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.market_data.backoff import (
    BackoffPolicy,
    ReconnectTracker,
)
from app.crypto_arbitrage.market_data.local_book import (
    BookLevelChange,
    LocalOrderBook,
)
from app.crypto_arbitrage.market_data.metrics import (
    ConnectorMetrics,
)
from app.crypto_arbitrage.market_data.rate_limiter import (
    TokenBucketRateLimiter,
)
from app.crypto_arbitrage.market_data.stream_manager import (
    BookStreamManager,
    StreamOutcome,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)


class FakeClock:
    def __init__(self, value="0"):
        self.value = Decimal(value)

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += Decimal(seconds)


# ---------------------------------------------------------------
# Backoff
# ---------------------------------------------------------------


def test_backoff_grows_exponentially():
    policy = BackoffPolicy.create(
        initial_seconds="1",
        maximum_seconds="60",
        multiplier="2",
    )

    assert policy.base_delay(1) == Decimal("1")
    assert policy.base_delay(2) == Decimal("2")
    assert policy.base_delay(3) == Decimal("4")
    assert policy.base_delay(4) == Decimal("8")


def test_backoff_respects_ceiling():
    policy = BackoffPolicy.create(
        initial_seconds="1",
        maximum_seconds="5",
        multiplier="2",
    )

    assert policy.base_delay(10) == Decimal("5")


def test_backoff_attempt_starts_at_one():
    policy = BackoffPolicy.create()

    with pytest.raises(DomainValidationError):
        policy.base_delay(0)


def test_jitter_only_reduces_never_exceeds_ceiling():
    policy = BackoffPolicy.create(
        initial_seconds="10",
        maximum_seconds="10",
        multiplier="1",
        jitter_ratio="0.25",
    )

    full = policy.delay_for(1, random_value="1")
    minimum = policy.delay_for(1, random_value="0")

    assert full == Decimal("10")
    assert minimum == Decimal("7.50")
    assert minimum < full <= policy.maximum_seconds


def test_jitter_is_deterministic_for_same_input():
    policy = BackoffPolicy.create()

    first = policy.delay_for(3, random_value="0.5")
    second = policy.delay_for(3, random_value="0.5")

    assert first == second


def test_backoff_validates_random_value_range():
    policy = BackoffPolicy.create()

    with pytest.raises(DomainValidationError):
        policy.delay_for(1, random_value="1.5")


def test_backoff_rejects_maximum_below_initial():
    with pytest.raises(DomainValidationError):
        BackoffPolicy.create(
            initial_seconds="10",
            maximum_seconds="1",
        )


def test_backoff_rejects_multiplier_below_one():
    with pytest.raises(DomainValidationError):
        BackoffPolicy.create(multiplier="0.5")


def test_backoff_rejects_jitter_out_of_range():
    with pytest.raises(DomainValidationError):
        BackoffPolicy.create(jitter_ratio="1.5")


def test_tracker_escalates_and_counts():
    tracker = ReconnectTracker(
        BackoffPolicy.create(
            initial_seconds="1",
            multiplier="2",
            jitter_ratio="0",
        )
    )

    assert tracker.next_delay() == Decimal("1")
    assert tracker.next_delay() == Decimal("2")
    assert tracker.next_delay() == Decimal("4")
    assert tracker.total_reconnects == 3


def test_tracker_reset_restarts_escalation_but_keeps_total():
    tracker = ReconnectTracker(
        BackoffPolicy.create(
            initial_seconds="1",
            multiplier="2",
            jitter_ratio="0",
        )
    )

    tracker.next_delay()
    tracker.next_delay()
    tracker.reset()

    assert tracker.attempt == 0
    assert tracker.next_delay() == Decimal("1")
    assert tracker.total_reconnects == 3


# ---------------------------------------------------------------
# Rate limiter
# ---------------------------------------------------------------


def test_bucket_starts_full():
    limiter = TokenBucketRateLimiter(
        capacity="3",
        refill_per_second="1",
        clock=FakeClock(),
    )

    assert limiter.available_tokens == Decimal("3")


def test_bucket_consumes_and_rejects_when_empty():
    limiter = TokenBucketRateLimiter(
        capacity="2",
        refill_per_second="1",
        clock=FakeClock(),
    )

    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is True
    assert limiter.try_acquire() is False
    assert limiter.allowed_total == 2
    assert limiter.rejected_total == 1


def test_bucket_refills_over_time():
    clock = FakeClock()

    limiter = TokenBucketRateLimiter(
        capacity="2",
        refill_per_second="1",
        clock=clock,
    )

    limiter.try_acquire()
    limiter.try_acquire()

    assert limiter.try_acquire() is False

    clock.advance("1")

    assert limiter.try_acquire() is True


def test_bucket_never_exceeds_capacity():
    clock = FakeClock()

    limiter = TokenBucketRateLimiter(
        capacity="2",
        refill_per_second="10",
        clock=clock,
    )

    clock.advance("100")

    assert limiter.available_tokens == Decimal("2")


def test_bucket_reports_wait_time():
    clock = FakeClock()

    limiter = TokenBucketRateLimiter(
        capacity="1",
        refill_per_second="2",
        clock=clock,
    )

    limiter.try_acquire()

    assert limiter.seconds_until_available() == Decimal(
        "0.5"
    )


def test_bucket_wait_is_zero_when_available():
    limiter = TokenBucketRateLimiter(
        capacity="5",
        refill_per_second="1",
        clock=FakeClock(),
    )

    assert limiter.seconds_until_available() == Decimal("0")


def test_bucket_rejects_request_larger_than_capacity():
    limiter = TokenBucketRateLimiter(
        capacity="2",
        refill_per_second="1",
        clock=FakeClock(),
    )

    with pytest.raises(DomainValidationError):
        limiter.try_acquire("5")


def test_bucket_survives_backward_clock():
    clock = FakeClock("100")

    limiter = TokenBucketRateLimiter(
        capacity="2",
        refill_per_second="1",
        clock=clock,
    )

    limiter.try_acquire()
    clock.value = Decimal("50")

    assert limiter.available_tokens == Decimal("1")


# ---------------------------------------------------------------
# Metricas
# ---------------------------------------------------------------


def test_metrics_expose_documented_names():
    metrics = ConnectorMetrics("BINANCE")
    payload = metrics.to_dict()

    for key in (
        "market_data_messages_total",
        "market_data_gap_total",
        "market_data_reconnect_total",
        "orderbook_age_ms",
        "exchange_to_receive_latency_ms",
        "local_processing_latency_ms",
        "connector_error_total",
        "connector_rate_limit_total",
    ):
        assert key in payload


def test_metrics_start_disconnected_and_unhealthy():
    metrics = ConnectorMetrics("BINANCE")

    assert metrics.state is ConnectorState.DISCONNECTED
    assert metrics.is_healthy is False


def test_metrics_gap_degrades_state():
    metrics = ConnectorMetrics("BINANCE")
    metrics.set_state(ConnectorState.READY)

    metrics.record_gap("buraco na sequencia")

    assert metrics.state is ConnectorState.DEGRADED
    assert metrics.is_healthy is False
    assert metrics.last_error == "buraco na sequencia"


def test_metrics_recover_health_after_resync():
    metrics = ConnectorMetrics("BINANCE")

    metrics.record_gap("gap")
    metrics.set_state(ConnectorState.READY)

    assert metrics.is_healthy is True
    assert metrics.gap_total == 1


def test_metrics_declare_read_only():
    payload = ConnectorMetrics("BINANCE").to_dict()

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True


# ---------------------------------------------------------------
# Transporte
# ---------------------------------------------------------------


class FakeRest:
    def __init__(self, payload):
        self.payload = payload
        self.calls = []

    async def get_json(self, url, *, params=None):
        self.calls.append((url, params))
        return self.payload


class FakeWebSocket:
    def __init__(self, messages):
        self.messages = list(messages)
        self.sent = []
        self._connected = False

    @property
    def is_connected(self):
        return self._connected

    async def connect(self, url):
        self._connected = True

    async def send_json(self, payload):
        self.sent.append(payload)

    async def receive_json(self):
        return self.messages.pop(0)

    async def close(self):
        self._connected = False


def test_fakes_satisfy_transport_protocols():
    assert isinstance(FakeRest({}), RestTransport)
    assert isinstance(
        FakeWebSocket([]),
        WebSocketTransport,
    )


# ---------------------------------------------------------------
# Orquestracao
# ---------------------------------------------------------------


def _manager(adapter=None, instrument="BTCUSDT"):
    adapter = adapter or BinanceSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        instrument,
        sequence_mode=adapter.sequence_mode,
    )

    return BookStreamManager(adapter, book)


def _binance_depth(first, final, bids=(), asks=()):
    return {
        "e": "depthUpdate",
        "s": "BTCUSDT",
        "U": first,
        "u": final,
        "b": [list(level) for level in bids],
        "a": [list(level) for level in asks],
    }


def _seed(manager, update_id=100):
    manager.book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=update_id,
        received_timestamp=MOMENT,
    )


def test_manager_ignores_control_message():
    manager = _manager()

    result = manager.handle_message(
        {"result": None, "id": 1},
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.MESSAGE_IGNORED
    assert manager.metrics.messages_total == 1


def test_manager_applies_delta_and_counts():
    manager = _manager()
    _seed(manager)

    result = manager.handle_message(
        _binance_depth(101, 105, bids=[("99", "1")]),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.DELTA_APPLIED
    assert manager.metrics.deltas_applied_total == 1
    assert manager.book.best_bid() == Decimal("99")


def test_manager_reports_ignored_replay():
    manager = _manager()
    _seed(manager)

    result = manager.handle_message(
        _binance_depth(1, 50),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.DELTA_IGNORED
    assert manager.metrics.deltas_ignored_total == 1


def test_manager_turns_gap_into_resync_not_exception():
    manager = _manager()
    _seed(manager)

    result = manager.handle_message(
        _binance_depth(200, 210),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.RESYNC_REQUIRED
    assert result.needs_resync is True
    assert manager.metrics.gap_total == 1
    assert manager.book.needs_resync is True


def test_manager_turns_corruption_into_resync():
    manager = _manager()

    manager.book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=100,
        received_timestamp=MOMENT,
    )

    manager.handle_message(
        _binance_depth(
            101,
            102,
            bids=[("100", "1")],
            asks=[("110", "1")],
        ),
        received_timestamp=MOMENT,
    )

    result = manager.handle_message(
        _binance_depth(103, 104, bids=[("120", "1")]),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.RESYNC_REQUIRED
    assert manager.metrics.corrupted_total == 1


def test_manager_reports_error_for_malformed_payload():
    manager = _manager()
    _seed(manager)

    result = manager.handle_message(
        {"e": "depthUpdate", "s": "BTCUSDT", "u": 101},
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.ERROR
    assert manager.metrics.error_total == 1


def test_manager_applies_snapshot_from_stream():
    adapter = BybitSpotAdapter()

    manager = _manager(adapter=adapter)

    result = manager.handle_message(
        {
            "topic": "orderbook.50.BTCUSDT",
            "type": "snapshot",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["99", "1"]],
                "a": [["101", "1"]],
                "u": 10,
                "seq": 1,
            },
        },
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.SNAPSHOT_APPLIED
    assert manager.metrics.snapshots_total == 1
    assert manager.book.is_ready is True


def test_manager_records_exchange_latency():
    adapter = BybitSpotAdapter()
    manager = _manager(adapter=adapter)

    manager.handle_message(
        {
            "type": "snapshot",
            "ts": 1785628800000,
            "data": {
                "s": "BTCUSDT",
                "b": [["99", "1"]],
                "a": [["101", "1"]],
                "u": 10,
                "seq": 1,
            },
        },
        received_timestamp=MOMENT
        + timedelta(milliseconds=40),
    )

    assert (
        manager.metrics.exchange_to_receive.last
        == Decimal("40")
    )


def test_manager_records_processing_latency():
    manager = _manager()
    _seed(manager)

    manager.handle_message(
        _binance_depth(101, 102),
        received_timestamp=MOMENT,
        processed_at=MOMENT + timedelta(milliseconds=7),
    )

    assert (
        manager.metrics.local_processing.last
        == Decimal("7")
    )


def test_pricing_blocked_while_book_not_ready():
    manager = _manager()

    snapshot, verdict = manager.snapshot_for_pricing(MOMENT)

    assert snapshot is None
    assert verdict.is_fresh is False
    assert "CONNECTING" in verdict.reason


def test_pricing_blocked_when_stale():
    manager = _manager()

    manager.book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=1,
        received_timestamp=MOMENT,
    )

    snapshot, verdict = manager.snapshot_for_pricing(
        MOMENT + timedelta(seconds=30)
    )

    assert snapshot is None
    assert verdict.is_fresh is False
    assert "excede o limite" in verdict.reason


def test_pricing_allowed_when_ready_and_fresh():
    manager = _manager()

    manager.book.apply_snapshot(
        bids=[],
        asks=[],
        update_id=1,
        received_timestamp=MOMENT,
    )

    snapshot, verdict = manager.snapshot_for_pricing(
        MOMENT + timedelta(milliseconds=50)
    )

    assert snapshot is not None
    assert verdict.is_fresh is True
    assert (
        manager.metrics.last_orderbook_age_ms
        == Decimal("50")
    )


def test_disconnect_forces_resync_and_counts_reconnect():
    manager = _manager()
    _seed(manager)

    manager.mark_disconnected("socket caiu")

    assert manager.book.needs_resync is True
    assert manager.metrics.reconnect_total == 1
    assert (
        manager.metrics.state
        is ConnectorState.DISCONNECTED
    )

    snapshot, verdict = manager.snapshot_for_pricing(MOMENT)

    assert snapshot is None


def test_resync_after_gap_restores_pricing():
    manager = _manager()
    _seed(manager)

    manager.handle_message(
        _binance_depth(500, 510),
        received_timestamp=MOMENT,
    )

    assert manager.book.needs_resync is True

    manager.book.apply_snapshot(
        bids=[
            BookLevelChange(
                price=Decimal("99"),
                quantity=Decimal("1"),
            )
        ],
        asks=[
            BookLevelChange(
                price=Decimal("101"),
                quantity=Decimal("1"),
            )
        ],
        update_id=510,
        received_timestamp=MOMENT,
    )

    snapshot, verdict = manager.snapshot_for_pricing(
        MOMENT + timedelta(milliseconds=10)
    )

    assert snapshot is not None
    assert verdict.is_fresh is True
    assert manager.book.stats.resync_count == 1


def test_status_is_serializable_and_declares_read_only():
    manager = _manager()
    _seed(manager)

    status = manager.status()

    assert status["book"]["venue_id"] == "BINANCE"
    assert status["metrics"]["read_only"] is True
    assert "freshness_limit_ms" in status
