"""Fase 19C2 - transportes concretos e sincronizacao inicial.

Nenhum teste abre socket nem faz requisicao real. O httpx e
exercitado com MockTransport, que percorre o caminho de parsing de
verdade, e o WebSocket recebe uma conexao dublada.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.crypto_arbitrage.connectors.binance import (
    BinanceSpotAdapter,
)
from app.crypto_arbitrage.connectors.bybit import (
    BybitSpotAdapter,
)
from app.crypto_arbitrage.connectors.http_transport import (
    HttpxRestTransport,
)
from app.crypto_arbitrage.connectors.transport import (
    RestTransport,
    WebSocketTransport,
)
from app.crypto_arbitrage.connectors.websocket_transport import (
    WebsocketsTransport,
)
from app.crypto_arbitrage.domain.errors import (
    RateLimitExceededError,
    SynchronizationError,
    TransportError,
)
from app.crypto_arbitrage.market_data.local_book import (
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
from app.crypto_arbitrage.market_data.synchronizer import (
    BookSynchronizer,
    SyncState,
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


# ---------------------------------------------------------------
# Transporte REST
# ---------------------------------------------------------------


def _rest_transport(handler, **kwargs):
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    )

    return HttpxRestTransport(client, **kwargs), client


def test_rest_transport_satisfies_protocol():
    transport, client = _rest_transport(
        lambda request: httpx.Response(200, json={})
    )

    assert isinstance(transport, RestTransport)

    asyncio.run(client.aclose())


def test_rest_transport_returns_parsed_json():
    def handler(request):
        return httpx.Response(
            200,
            json={"lastUpdateId": 42},
        )

    transport, client = _rest_transport(handler)

    async def scenario():
        payload = await transport.get_json(
            "https://api.example.com/depth",
            params={"symbol": "BTCUSDT"},
        )
        await client.aclose()
        return payload

    assert asyncio.run(scenario()) == {"lastUpdateId": 42}


def test_rest_transport_sends_params():
    seen = {}

    def handler(request):
        seen["url"] = str(request.url)
        return httpx.Response(200, json={})

    transport, client = _rest_transport(handler)

    async def scenario():
        await transport.get_json(
            "https://api.example.com/depth",
            params={"symbol": "BTCUSDT", "limit": 5000},
        )
        await client.aclose()

    asyncio.run(scenario())

    assert "symbol=BTCUSDT" in seen["url"]
    assert "limit=5000" in seen["url"]


def test_rest_transport_raises_on_http_error():
    metrics = ConnectorMetrics("BINANCE")

    transport, client = _rest_transport(
        lambda request: httpx.Response(500, text="boom"),
        metrics=metrics,
    )

    async def scenario():
        with pytest.raises(TransportError):
            await transport.get_json(
                "https://api.example.com/depth"
            )
        await client.aclose()

    asyncio.run(scenario())

    assert metrics.error_total == 1


def test_rest_transport_maps_429_to_rate_limit():
    metrics = ConnectorMetrics("BINANCE")

    transport, client = _rest_transport(
        lambda request: httpx.Response(429),
        metrics=metrics,
    )

    async def scenario():
        with pytest.raises(RateLimitExceededError):
            await transport.get_json(
                "https://api.example.com/depth"
            )
        await client.aclose()

    asyncio.run(scenario())

    assert metrics.rate_limit_total == 1
    assert metrics.error_total == 0


def test_rest_transport_raises_on_non_json():
    transport, client = _rest_transport(
        lambda request: httpx.Response(
            200,
            text="<html>nope</html>",
        )
    )

    async def scenario():
        with pytest.raises(TransportError):
            await transport.get_json(
                "https://api.example.com/depth"
            )
        await client.aclose()

    asyncio.run(scenario())


def test_rest_transport_raises_on_network_failure():
    def handler(request):
        raise httpx.ConnectError("sem rede")

    transport, client = _rest_transport(handler)

    async def scenario():
        with pytest.raises(TransportError):
            await transport.get_json(
                "https://api.example.com/depth"
            )
        await client.aclose()

    asyncio.run(scenario())


def test_rest_transport_blocks_before_reaching_the_venue():
    """O limite local recusa antes de gastar a cota da venue."""

    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={})

    limiter = TokenBucketRateLimiter(
        capacity="1",
        refill_per_second="1",
        clock=FakeClock(),
    )

    metrics = ConnectorMetrics("BINANCE")

    transport, client = _rest_transport(
        handler,
        rate_limiter=limiter,
        metrics=metrics,
    )

    async def scenario():
        await transport.get_json(
            "https://api.example.com/depth"
        )

        with pytest.raises(RateLimitExceededError):
            await transport.get_json(
                "https://api.example.com/depth"
            )

        await client.aclose()

    asyncio.run(scenario())

    assert len(calls) == 1
    assert metrics.rate_limit_total == 1


# ---------------------------------------------------------------
# Transporte WebSocket
# ---------------------------------------------------------------


class FakeConnection:
    def __init__(self, messages=()):
        self.messages = list(messages)
        self.sent = []
        self.closed = False

    async def send(self, raw):
        self.sent.append(raw)

    async def recv(self):
        if not self.messages:
            raise RuntimeError("sem mensagens")

        return self.messages.pop(0)

    async def close(self):
        self.closed = True


def _ws(messages=(), fail=False):
    connection = FakeConnection(messages)

    async def factory(url, **kwargs):
        if fail:
            raise RuntimeError("recusado")

        factory.url = url
        factory.kwargs = kwargs

        return connection

    return (
        WebsocketsTransport(connect_factory=factory),
        connection,
        factory,
    )


def test_ws_transport_satisfies_protocol():
    transport, _, _ = _ws()

    assert isinstance(transport, WebSocketTransport)


def test_ws_connect_passes_heartbeat_settings():
    transport, _, factory = _ws()

    asyncio.run(transport.connect("wss://example/ws"))

    assert transport.is_connected is True
    assert factory.url == "wss://example/ws"
    assert factory.kwargs["ping_interval"] == 20.0
    assert factory.kwargs["ping_timeout"] == 20.0


def test_ws_refuses_double_connect():
    transport, _, _ = _ws()

    async def scenario():
        await transport.connect("wss://example/ws")

        with pytest.raises(TransportError):
            await transport.connect("wss://example/ws")

    asyncio.run(scenario())


def test_ws_connect_failure_becomes_transport_error():
    transport, _, _ = _ws(fail=True)

    with pytest.raises(TransportError):
        asyncio.run(transport.connect("wss://example/ws"))

    assert transport.is_connected is False


def test_ws_send_and_receive_json():
    transport, connection, _ = _ws(
        messages=['{"type":"snapshot"}']
    )

    async def scenario():
        await transport.connect("wss://example/ws")
        await transport.send_json({"op": "subscribe"})
        return await transport.receive_json()

    payload = asyncio.run(scenario())

    assert payload == {"type": "snapshot"}
    assert connection.sent == ['{"op": "subscribe"}']


def test_ws_decodes_bytes_frames():
    transport, _, _ = _ws(messages=[b'{"type":"delta"}'])

    async def scenario():
        await transport.connect("wss://example/ws")
        return await transport.receive_json()

    assert asyncio.run(scenario()) == {"type": "delta"}


def test_ws_rejects_non_json_frame():
    transport, _, _ = _ws(messages=["pong"])

    async def scenario():
        await transport.connect("wss://example/ws")

        with pytest.raises(TransportError):
            await transport.receive_json()

    asyncio.run(scenario())


def test_ws_requires_connection_before_use():
    transport, _, _ = _ws()

    with pytest.raises(TransportError):
        asyncio.run(transport.receive_json())


def test_ws_close_is_idempotent():
    transport, connection, _ = _ws()

    async def scenario():
        await transport.connect("wss://example/ws")
        await transport.close()
        await transport.close()

    asyncio.run(scenario())

    assert connection.closed is True
    assert transport.is_connected is False


# ---------------------------------------------------------------
# Sincronizacao
# ---------------------------------------------------------------


def _sync(adapter=None, max_buffer=2000):
    adapter = adapter or BinanceSpotAdapter()

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    manager = BookStreamManager(adapter, book)

    return BookSynchronizer(
        adapter,
        manager,
        max_buffer=max_buffer,
    )


def _depth(first, final, bids=(), asks=()):
    return {
        "e": "depthUpdate",
        "s": "BTCUSDT",
        "U": first,
        "u": final,
        "b": [list(level) for level in bids],
        "a": [list(level) for level in asks],
    }


def _rest_depth(last_update_id, bids=(), asks=()):
    return {
        "lastUpdateId": last_update_id,
        "bids": [list(level) for level in bids],
        "asks": [list(level) for level in asks],
    }


def test_sync_starts_buffering():
    sync = _sync()

    assert sync.state is SyncState.BUFFERING
    assert sync.buffered_count == 0


def test_sync_rejects_invalid_buffer_size():
    adapter = BinanceSpotAdapter()
    book = LocalOrderBook(adapter.venue_id, "BTCUSDT")

    with pytest.raises(SynchronizationError):
        BookSynchronizer(
            adapter,
            BookStreamManager(adapter, book),
            max_buffer=0,
        )


def test_sync_buffers_deltas_before_snapshot():
    sync = _sync()

    sync.observe(
        _depth(101, 105),
        received_timestamp=MOMENT,
    )

    sync.observe(
        _depth(106, 110),
        received_timestamp=MOMENT,
    )

    assert sync.buffered_count == 2
    assert sync.first_buffered_update_id == 101
    assert sync.book.is_ready is False


def test_sync_applies_snapshot_and_replays_buffer():
    sync = _sync()

    sync.observe(
        _depth(101, 105, bids=[("99", "1")]),
        received_timestamp=MOMENT,
    )

    sync.observe(
        _depth(106, 110, bids=[("98", "2")]),
        received_timestamp=MOMENT,
    )

    result = sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(
                104,
                bids=[("97", "5")],
                asks=[("110", "1")],
            ),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.SNAPSHOT_APPLIED
    assert sync.state is SyncState.SYNCED
    assert sync.stats.replayed_total == 2
    assert sync.book.is_ready is True
    assert sync.book.best_bid() == Decimal("99")


def test_sync_discards_deltas_already_in_snapshot():
    sync = _sync()

    sync.observe(
        _depth(90, 95),
        received_timestamp=MOMENT,
    )

    sync.observe(
        _depth(101, 105, bids=[("99", "1")]),
        received_timestamp=MOMENT,
    )

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    assert sync.stats.discarded_total == 1
    assert sync.stats.replayed_total == 1
    assert sync.state is SyncState.SYNCED


def test_sync_refuses_snapshot_older_than_buffer():
    """O passo que a maioria das implementacoes esquece."""

    sync = _sync()

    sync.observe(
        _depth(500, 510),
        received_timestamp=MOMENT,
    )

    result = sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.RESYNC_REQUIRED
    assert sync.stats.snapshot_rejected_total == 1
    assert sync.state is SyncState.BUFFERING
    assert sync.book.is_ready is False


def test_sync_accepts_second_snapshot_after_rejection():
    sync = _sync()

    sync.observe(
        _depth(500, 510, bids=[("99", "1")]),
        received_timestamp=MOMENT,
    )

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    result = sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(505),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.SNAPSHOT_APPLIED
    assert sync.state is SyncState.SYNCED
    assert sync.stats.snapshot_attempts == 2


def test_sync_overflow_fails_closed():
    sync = _sync(max_buffer=2)

    for index in range(3):
        result = sync.observe(
            _depth(100 + index, 100 + index),
            received_timestamp=MOMENT,
        )

    assert result.outcome is StreamOutcome.RESYNC_REQUIRED
    assert sync.state is SyncState.FAILED
    assert sync.stats.dropped_overflow_total == 1
    assert "estourou" in sync.failure_reason


def test_sync_uses_pushed_snapshot_and_skips_rest():
    """Bybit empurra snapshot na inscricao."""

    sync = _sync(adapter=BybitSpotAdapter())

    result = sync.observe(
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
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.SNAPSHOT_APPLIED
    assert sync.state is SyncState.SYNCED
    assert sync.buffered_count == 0


def test_sync_delegates_to_manager_once_synced():
    sync = _sync()

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    result = sync.observe(
        _depth(101, 105, bids=[("99", "1")]),
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.DELTA_APPLIED
    assert sync.book.best_bid() == Decimal("99")


def test_sync_returns_to_buffering_after_gap():
    sync = _sync()

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    result = sync.observe(
        _depth(500, 510),
        received_timestamp=MOMENT,
    )

    assert result.needs_resync is True
    assert sync.state is SyncState.BUFFERING


def test_sync_restart_invalidates_book():
    sync = _sync()

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(100),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    sync.restart("socket caiu")

    assert sync.state is SyncState.BUFFERING
    assert sync.book.needs_resync is True
    assert sync.manager.metrics.reconnect_total == 1


def test_sync_ignores_control_messages_while_buffering():
    sync = _sync()

    result = sync.observe(
        {"result": None, "id": 1},
        received_timestamp=MOMENT,
    )

    assert result.outcome is StreamOutcome.MESSAGE_IGNORED
    assert sync.buffered_count == 0


def test_sync_status_is_serializable():
    sync = _sync()

    sync.observe(
        _depth(101, 105),
        received_timestamp=MOMENT,
    )

    status = sync.status()

    assert status["state"] == SyncState.BUFFERING.value
    assert status["buffered_count"] == 1
    assert status["first_buffered_update_id"] == 101
    assert status["manager"]["metrics"]["read_only"] is True


def test_synced_book_can_price_after_full_flow():
    """Aceitacao: do zero ate precificar, sem tocar a rede."""

    sync = _sync()

    sync.observe(
        _depth(
            101,
            105,
            bids=[("99", "2")],
            asks=[("101", "2")],
        ),
        received_timestamp=MOMENT,
    )

    sync.apply_rest_snapshot(
        BinanceSpotAdapter().parse_rest_snapshot(
            _rest_depth(104),
            instrument_id="BTCUSDT",
        ),
        received_timestamp=MOMENT,
    )

    snapshot, verdict = (
        sync.manager.snapshot_for_pricing(
            MOMENT + timedelta(milliseconds=20)
        )
    )

    assert sync.state is SyncState.SYNCED
    assert snapshot is not None
    assert verdict.is_fresh is True
    assert snapshot.best_bid.price == Decimal("99")
