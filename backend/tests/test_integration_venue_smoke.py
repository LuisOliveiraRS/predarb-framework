"""Fumaca de integracao: adaptadores contra as venues reais.

TODOS os testes deste arquivo tocam a rede e estao marcados com
`integration`. O `pytest.ini` desliga esse marcador por padrao, entao
eles nao rodam na suite normal. Para exercita-los:

```powershell
.venv\\Scripts\\python.exe -m pytest -m integration -v
```

Por que existem: as Fases 18 a 20A foram construidas sobre fixtures
escritas a partir da documentacao oficial. Documentacao e realidade
divergem em detalhes que quebram parser - um campo que vem como string
onde se esperava numero, um nivel de book com formato diferente, um
simbolo que nao normaliza. Este arquivo e a unica coisa que confronta o
codigo com a resposta de verdade.

Somente endpoints publicos. Nenhuma credencial, nenhuma chave, nenhuma
ordem. Apenas leitura.
"""

import asyncio
from datetime import datetime, timezone

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
from app.crypto_arbitrage.connectors.okx import (
    OkxSpotAdapter,
)
from app.crypto_arbitrage.connectors.venue_adapter import (
    StreamMessageKind,
)
from app.crypto_arbitrage.connectors.websocket_transport import (
    WebsocketsTransport,
)
from app.crypto_arbitrage.domain.enums import (
    InstrumentStatus,
    Side,
)
from app.crypto_arbitrage.market_data.local_book import (
    LocalOrderBook,
)
from app.crypto_arbitrage.market_data.stream_manager import (
    BookStreamManager,
)
from app.crypto_arbitrage.market_data.synchronizer import (
    BookSynchronizer,
    SyncState,
)


pytestmark = pytest.mark.integration


TIMEOUT = 20.0
WS_MESSAGE_BUDGET = 12
WS_TIMEOUT = 25.0


def _utc_now():
    return datetime.now(timezone.utc)


async def _fetch(url, params=None):
    async with httpx.AsyncClient(
        timeout=TIMEOUT,
        headers={"User-Agent": "predarb-smoke/1.0"},
    ) as client:
        transport = HttpxRestTransport(client)

        return await transport.get_json(
            url,
            params=params,
        )


def _run(coro):
    return asyncio.run(coro)


# ---------------------------------------------------------------
# Binance
# ---------------------------------------------------------------


def test_binance_instruments_parse_against_real_payload():
    payload = _run(
        _fetch(
            "https://api.binance.com/api/v3/exchangeInfo",
            {"symbol": "BTCUSDT"},
        )
    )

    result = BinanceSpotAdapter().parse_instruments(payload)

    assert result.skipped == (), (
        "Instrumentos descartados: "
        f"{[item.to_dict() for item in result.skipped]}"
    )

    assert len(result.instruments) == 1

    instrument = result.instruments[0]

    assert instrument.instrument_id == "BTCUSDT"
    assert instrument.pair.canonical == "BTC/USDT"
    assert instrument.status is InstrumentStatus.TRADING
    assert instrument.price_tick > 0
    assert instrument.min_notional > 0


def test_binance_depth_snapshot_parses_and_prices():
    payload = _run(
        _fetch(
            "https://api.binance.com/api/v3/depth",
            {"symbol": "BTCUSDT", "limit": 100},
        )
    )

    adapter = BinanceSpotAdapter()

    snapshot = adapter.parse_rest_snapshot(
        payload,
        instrument_id="BTCUSDT",
    )

    assert snapshot.update_id is not None
    assert len(snapshot.bids) > 0
    assert len(snapshot.asks) > 0

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    now = _utc_now()

    book.apply_snapshot(
        bids=snapshot.bids,
        asks=snapshot.asks,
        update_id=snapshot.update_id,
        received_timestamp=now,
    )

    exported = book.to_snapshot(received_timestamp=now)

    assert exported.best_bid.price < exported.best_ask.price

    priced = exported.vwap_for_quantity(
        Side.BUY,
        "0.001",
    )

    assert priced.vwap > 0


# ---------------------------------------------------------------
# OKX
# ---------------------------------------------------------------


def test_okx_instruments_parse_against_real_payload():
    payload = _run(
        _fetch(
            "https://www.okx.com/api/v5/public/instruments",
            {"instType": "SPOT"},
        )
    )

    result = OkxSpotAdapter().parse_instruments(payload)

    assert len(result.instruments) > 0

    by_id = {
        item.instrument_id: item
        for item in result.instruments
    }

    assert "BTC-USDT" in by_id

    btc = by_id["BTC-USDT"]

    assert btc.pair.canonical == "BTC/USDT"
    assert btc.status is InstrumentStatus.TRADING
    assert btc.price_tick > 0


def test_okx_books_snapshot_parses_and_prices():
    payload = _run(
        _fetch(
            "https://www.okx.com/api/v5/market/books",
            {"instId": "BTC-USDT", "sz": "50"},
        )
    )

    adapter = OkxSpotAdapter()

    snapshot = adapter.parse_rest_snapshot(
        payload,
        instrument_id="BTC-USDT",
    )

    assert len(snapshot.bids) > 0
    assert len(snapshot.asks) > 0

    book = LocalOrderBook(
        adapter.venue_id,
        "BTC-USDT",
        sequence_mode=adapter.sequence_mode,
    )

    now = _utc_now()

    book.apply_snapshot(
        bids=snapshot.bids,
        asks=snapshot.asks,
        update_id=snapshot.update_id,
        received_timestamp=now,
    )

    exported = book.to_snapshot(received_timestamp=now)

    assert exported.best_bid.price < exported.best_ask.price


# ---------------------------------------------------------------
# Bybit
# ---------------------------------------------------------------


def test_bybit_instruments_parse_against_real_payload():
    payload = _run(
        _fetch(
            "https://api.bybit.com/v5/market/instruments-info",
            {"category": "spot", "symbol": "BTCUSDT"},
        )
    )

    result = BybitSpotAdapter().parse_instruments(payload)

    assert result.skipped == (), (
        "Instrumentos descartados: "
        f"{[item.to_dict() for item in result.skipped]}"
    )

    assert len(result.instruments) == 1

    instrument = result.instruments[0]

    assert instrument.instrument_id == "BTCUSDT"
    assert instrument.pair.canonical == "BTC/USDT"
    assert instrument.status is InstrumentStatus.TRADING
    assert instrument.price_tick > 0


def test_bybit_orderbook_snapshot_parses_and_prices():
    payload = _run(
        _fetch(
            "https://api.bybit.com/v5/market/orderbook",
            {
                "category": "spot",
                "symbol": "BTCUSDT",
                "limit": 50,
            },
        )
    )

    adapter = BybitSpotAdapter()

    snapshot = adapter.parse_rest_snapshot(
        payload,
        instrument_id="BTCUSDT",
    )

    assert len(snapshot.bids) > 0
    assert len(snapshot.asks) > 0

    book = LocalOrderBook(
        adapter.venue_id,
        "BTCUSDT",
        sequence_mode=adapter.sequence_mode,
    )

    now = _utc_now()

    book.apply_snapshot(
        bids=snapshot.bids,
        asks=snapshot.asks,
        update_id=snapshot.update_id,
        received_timestamp=now,
    )

    exported = book.to_snapshot(received_timestamp=now)

    assert exported.best_bid.price < exported.best_ask.price


# ---------------------------------------------------------------
# WebSocket: onde mora o risco de sequencia
# ---------------------------------------------------------------


async def _drain(transport, url, subscribe, adapter, book_id):
    """Conecta, inscreve e processa algumas mensagens reais."""

    book = LocalOrderBook(
        adapter.venue_id,
        book_id,
        sequence_mode=adapter.sequence_mode,
    )

    manager = BookStreamManager(adapter, book)
    sync = BookSynchronizer(adapter, manager)

    kinds = []

    await transport.connect(url)

    try:
        if subscribe is not None:
            await transport.send_json(subscribe)

        for _ in range(WS_MESSAGE_BUDGET):
            payload = await asyncio.wait_for(
                transport.receive_json(),
                timeout=WS_TIMEOUT,
            )

            message = adapter.parse_stream_message(payload)
            kinds.append(message.kind)

            sync.observe(
                payload,
                received_timestamp=_utc_now(),
            )
    finally:
        await transport.close()

    return sync, kinds


def test_binance_depth_stream_parses_real_messages():
    adapter = BinanceSpotAdapter()

    sync, kinds = _run(
        _drain(
            WebsocketsTransport(),
            "wss://stream.binance.com:9443/ws/btcusdt@depth",
            None,
            adapter,
            "BTCUSDT",
        )
    )

    deltas = [
        kind
        for kind in kinds
        if kind is StreamMessageKind.DELTA
    ]

    assert len(deltas) > 0, (
        "Nenhum depthUpdate reconhecido. Kinds: "
        f"{[k.value for k in kinds]}"
    )

    # Sem snapshot REST, o sincronizador deve seguir
    # bufferizando: e exatamente o comportamento correto.
    assert sync.state is SyncState.BUFFERING
    assert sync.buffered_count > 0
    assert sync.first_buffered_update_id is not None


def test_okx_books_stream_parses_real_messages():
    adapter = OkxSpotAdapter()

    subscribe = {
        "op": "subscribe",
        "args": [
            {"channel": "books", "instId": "BTC-USDT"}
        ],
    }

    sync, kinds = _run(
        _drain(
            WebsocketsTransport(),
            "wss://ws.okx.com:8443/ws/v5/public",
            subscribe,
            adapter,
            "BTC-USDT",
        )
    )

    assert StreamMessageKind.SNAPSHOT in kinds, (
        "OKX deveria empurrar snapshot na inscricao. Kinds: "
        f"{[k.value for k in kinds]}"
    )

    # Snapshot empurrado dispensa o REST e sincroniza direto.
    assert sync.state is SyncState.SYNCED
    assert sync.book.is_ready is True


def test_bybit_orderbook_stream_parses_real_messages():
    adapter = BybitSpotAdapter()

    subscribe = {
        "op": "subscribe",
        "args": ["orderbook.50.BTCUSDT"],
    }

    sync, kinds = _run(
        _drain(
            WebsocketsTransport(),
            "wss://stream.bybit.com/v5/public/spot",
            subscribe,
            adapter,
            "BTCUSDT",
        )
    )

    assert StreamMessageKind.SNAPSHOT in kinds, (
        "Bybit deveria empurrar snapshot na inscricao. "
        f"Kinds: {[k.value for k in kinds]}"
    )

    assert sync.state is SyncState.SYNCED
    assert sync.book.is_ready is True


def test_bybit_applies_real_deltas_without_corruption():
    """O livro real sobrevive a uma rajada de deltas.

    Nao afirma nada sobre deteccao de gap: em MONOTONIC ela nao
    existe, e `gap_total == 0` seria tautologico. O que se
    verifica aqui e o que pode falhar de verdade - deltas
    aplicados de fato, livro consistente e nao cruzado.
    """

    adapter = BybitSpotAdapter()

    subscribe = {
        "op": "subscribe",
        "args": ["orderbook.50.BTCUSDT"],
    }

    sync, _ = _run(
        _drain(
            WebsocketsTransport(),
            "wss://stream.bybit.com/v5/public/spot",
            subscribe,
            adapter,
            "BTCUSDT",
        )
    )

    assert sync.state is SyncState.SYNCED
    assert sync.manager.metrics.deltas_applied_total > 0
    assert sync.manager.metrics.corrupted_total == 0
    assert sync.book.needs_resync is False
    assert sync.book.best_bid() < sync.book.best_ask()
