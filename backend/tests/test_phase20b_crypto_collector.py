"""Fase 20B - coletor do scanner cripto."""

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import httpx
import pytest

from app.core.settings import Settings
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
from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
)
from app.crypto_arbitrage.domain.symbols import build_pair
from app.crypto_arbitrage.services.book_source import (
    RestBookSource,
)
from app.crypto_arbitrage.services.factory import (
    build_scanner_service,
    parse_taker_fees,
    parse_venues,
)
from app.crypto_arbitrage.services.scanner_service import (
    CryptoScannerService,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)

PAIR = build_pair("BTC", "USDT")


# ---------------------------------------------------------------
# Nomenclatura e endpoints por venue
# ---------------------------------------------------------------


def test_each_venue_names_the_same_pair_differently():
    assert (
        BinanceSpotAdapter().instrument_id_for(PAIR)
        == "BTCUSDT"
    )
    assert (
        OkxSpotAdapter().instrument_id_for(PAIR)
        == "BTC-USDT"
    )
    assert (
        BybitSpotAdapter().instrument_id_for(PAIR)
        == "BTCUSDT"
    )


def test_depth_requests_use_each_venue_contract():
    url, params = BinanceSpotAdapter().depth_request(
        "BTCUSDT",
        50,
    )

    assert url.endswith("/api/v3/depth")
    assert params == {"symbol": "BTCUSDT", "limit": 50}

    url, params = OkxSpotAdapter().depth_request(
        "BTC-USDT",
        50,
    )

    assert url.endswith("/api/v5/market/books")
    assert params == {"instId": "BTC-USDT", "sz": "50"}

    url, params = BybitSpotAdapter().depth_request(
        "BTCUSDT",
        50,
    )

    assert url.endswith("/v5/market/orderbook")
    assert params["category"] == "spot"


# ---------------------------------------------------------------
# RestBookSource
# ---------------------------------------------------------------


def _binance_depth(bid, ask):
    return {
        "lastUpdateId": 1,
        "bids": [[bid, "5"]],
        "asks": [[ask, "5"]],
    }


def _source(payload, adapter=None, depth=50):
    adapter = adapter or BinanceSpotAdapter()

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(
                200,
                json=payload,
            )
        )
    )

    return (
        RestBookSource(
            adapter,
            HttpxRestTransport(client),
            depth=depth,
        ),
        client,
    )


def test_book_source_returns_validated_snapshot():
    source, client = _source(
        _binance_depth("99", "101")
    )

    async def scenario():
        snapshot = await source.fetch_snapshot(
            PAIR,
            received_timestamp=MOMENT,
        )
        await client.aclose()
        return snapshot

    snapshot = asyncio.run(scenario())

    assert snapshot.venue_id == "BINANCE"
    assert snapshot.instrument_id == "BTCUSDT"
    assert snapshot.best_bid.price == Decimal("99")
    assert snapshot.best_ask.price == Decimal("101")


def test_book_source_rejects_crossed_book_from_venue():
    """Book cruzado vindo da venue nao vira oportunidade."""

    source, client = _source(
        _binance_depth("105", "101")
    )

    async def scenario():
        with pytest.raises(CryptoArbitrageError):
            await source.fetch_snapshot(
                PAIR,
                received_timestamp=MOMENT,
            )
        await client.aclose()

    asyncio.run(scenario())


def test_book_source_requires_positive_depth():
    with pytest.raises(CryptoArbitrageError):
        RestBookSource(
            BinanceSpotAdapter(),
            object(),
            depth=0,
        )


# ---------------------------------------------------------------
# Servico e ciclo
# ---------------------------------------------------------------


class FakeSource:
    """Dubla `RestBookSource`, inclusive honrando o timestamp.

    Carimbar o book com o instante que o servico passa e o que
    torna o teste realista: o coletor usa o relogio de verdade, e
    fixture com hora fixa chegaria stale.
    """

    def __init__(
        self,
        venue_id,
        bid=None,
        ask=None,
        error=None,
        fixed_timestamp=None,
    ):
        self.venue_id = venue_id
        self.bid = bid
        self.ask = ask
        self._error = error
        self._fixed_timestamp = fixed_timestamp
        self.calls = 0

    def instrument_id_for(self, pair):
        return "BTCUSDT"

    async def fetch_snapshot(
        self,
        pair,
        *,
        received_timestamp=None,
    ):
        self.calls += 1

        if self._error is not None:
            raise self._error

        stamp = (
            self._fixed_timestamp
            or received_timestamp
            or datetime.now(timezone.utc)
        )

        return _snapshot(
            self.venue_id,
            self.bid,
            self.ask,
            received=stamp,
        )


def _snapshot(venue, bid, ask, received=None):
    from app.crypto_arbitrage.domain.models import (
        OrderBookLevel,
        OrderBookSnapshot,
    )

    return OrderBookSnapshot(
        venue_id=venue,
        instrument_id="BTCUSDT",
        bids=(
            OrderBookLevel(
                price=Decimal(bid),
                quantity=Decimal("10"),
            ),
        ),
        asks=(
            OrderBookLevel(
                price=Decimal(ask),
                quantity=Decimal("10"),
            ),
        ),
        exchange_timestamp=received or MOMENT,
        received_timestamp=received or MOMENT,
    )


def _service(sources, enabled=True, **overrides):
    from app.crypto_arbitrage.domain.fees import (
        FeeRate,
        FeeSchedule,
    )
    from app.crypto_arbitrage.market_data.freshness import (
        FreshnessPolicy,
    )
    from app.crypto_arbitrage.opportunities.cex_cex import (
        CexCexScanner,
    )
    from app.crypto_arbitrage.opportunities.profitability import (
        CostModel,
    )

    schedule = FeeSchedule()

    for venue_id in sources:
        schedule.register(
            FeeRate(
                venue_id=venue_id,
                instrument_id="BTCUSDT",
                maker_rate=Decimal("0.001"),
                taker_rate=Decimal("0.001"),
                source="test",
                effective_at=MOMENT - timedelta(days=1),
            )
        )

    scanner = CexCexScanner(
        fee_schedule=schedule,
        cost_model=CostModel.create(**overrides),
        freshness=FreshnessPolicy.create(
            max_age_ms=5000
        ),
    )

    return CryptoScannerService(
        scanner=scanner,
        sources=sources,
        pair=PAIR,
        quantity="1",
        enabled=enabled,
    )


def test_disabled_service_skips_without_collecting():
    source = FakeSource("BINANCE", "100", "100.5")

    service = _service(
        {"BINANCE": source},
        enabled=False,
    )

    result = service.run_task()

    assert result["last_status"] == "DISABLED"
    assert result["skipped"] == 1
    assert source.calls == 0


def test_cycle_collects_and_finds_opportunity():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5"),
            "OKX": FakeSource("OKX", "105", "105.5"),
        }
    )

    result = service.run_task()

    assert result["last_status"] == "READY"
    assert result["successes"] == 1
    assert result["last_venues_collected"] == 2
    assert result["last_opportunities"] >= 1


def test_partial_venue_failure_does_not_stop_the_cycle():
    """Uma venue fora do ar nao impede comparar as demais."""

    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5"),
            "OKX": FakeSource("OKX", "105", "105.5"),
            "BYBIT": FakeSource("BYBIT", error=RuntimeError("timeout")),
        }
    )

    result = service.run_task()

    assert result["last_status"] == "READY"
    assert result["last_venues_collected"] == 2
    assert "BYBIT" in result["last_venue_errors"]
    assert "timeout" in result["last_venue_errors"]["BYBIT"]


def test_all_venues_failing_reports_no_books():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", error=RuntimeError("fora")),
            "OKX": FakeSource("OKX", error=RuntimeError("fora")),
        }
    )

    result = service.run_task()

    assert result["last_status"] == "NO_BOOKS"
    assert result["last_opportunities"] == 0
    assert len(result["last_venue_errors"]) == 2


def test_snapshot_is_warming_up_before_first_cycle():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5")
        }
    )

    payload = service.snapshot()

    assert payload["status"] == "WARMING_UP"
    assert payload["snapshot_available"] is False
    assert payload["read_only"] is True


def test_reading_snapshot_never_triggers_collection():
    """Licao da Fase 17: ler nao coleta."""

    source = FakeSource("BINANCE", "100", "100.5")

    other = FakeSource("OKX", "105", "105.5")

    service = _service(
        {"BINANCE": source, "OKX": other}
    )

    service.run_task()

    calls_after_cycle = source.calls

    service.snapshot()
    service.snapshot()
    service.snapshot()

    assert source.calls == calls_after_cycle


def test_snapshot_serves_last_report():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5"),
            "OKX": FakeSource("OKX", "105", "105.5"),
        }
    )

    service.run_task()

    payload = service.snapshot()

    assert payload["status"] == "READY"
    assert payload["served_from_snapshot"] is True
    assert payload["opportunity_count"] >= 1
    assert payload["execution_authorized"] is False
    assert payload["order_submission_available"] is False


def test_status_declares_safety_flags():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5")
        }
    )

    status = service.status()

    assert status["read_only"] is True
    assert status["market_data_only"] is True
    assert status["execution_authorized"] is False
    assert status["financial_execution"] is False
    assert status["wallet_signing"] is False
    assert status["private_key_access"] is False
    assert status["pair"] == "BTC/USDT"


def test_stale_book_is_excluded_by_the_scanner():
    service = _service(
        {
            "BINANCE": FakeSource("BINANCE", "100", "100.5"),
            "OKX": FakeSource(
                "OKX",
                "105",
                "105.5",
                fixed_timestamp=MOMENT - timedelta(hours=1),
            ),
        }
    )

    service.run_task()

    payload = service.snapshot()

    assert payload["opportunity_count"] == 0
    assert any(
        item["stage"] == "freshness"
        for item in payload["rejected"]
    )


# ---------------------------------------------------------------
# Configuracao
# ---------------------------------------------------------------


def test_parse_helpers():
    assert parse_venues(" binance , okx ") == [
        "BINANCE",
        "OKX",
    ]

    assert parse_taker_fees(
        "BINANCE:0.001, OKX:0.0008"
    ) == {"BINANCE": "0.001", "OKX": "0.0008"}


def test_scanner_disabled_by_default():
    config = Settings()

    assert config.CRYPTO_SCANNER_ENABLED is False


def test_enabled_scanner_requires_two_venues():
    with pytest.raises(ValueError):
        Settings(
            CRYPTO_SCANNER_ENABLED=True,
            CRYPTO_SCANNER_VENUES="BINANCE",
        )


def test_enabled_scanner_requires_fee_for_every_venue():
    with pytest.raises(ValueError) as excinfo:
        Settings(
            CRYPTO_SCANNER_ENABLED=True,
            CRYPTO_SCANNER_VENUES="BINANCE,OKX",
            CRYPTO_SCANNER_TAKER_FEES="BINANCE:0.001",
        )

    assert "OKX" in str(excinfo.value)


def test_interval_is_bounded():
    with pytest.raises(ValueError):
        Settings(CRYPTO_SCANNER_INTERVAL_SECONDS=5)

    with pytest.raises(ValueError):
        Settings(CRYPTO_SCANNER_INTERVAL_SECONDS=99999)


def test_quantity_must_be_positive_decimal():
    with pytest.raises(ValueError):
        Settings(CRYPTO_SCANNER_QUANTITY="0")

    with pytest.raises(ValueError):
        Settings(CRYPTO_SCANNER_QUANTITY="abc")


def test_ratios_are_bounded():
    with pytest.raises(ValueError):
        Settings(CRYPTO_SCANNER_SLIPPAGE_RATIO="0.9")

    with pytest.raises(ValueError):
        Settings(
            CRYPTO_SCANNER_SAFETY_BUFFER_RATIO="-0.1"
        )


def test_fee_outside_range_is_refused():
    with pytest.raises(ValueError):
        Settings(
            CRYPTO_SCANNER_TAKER_FEES="BINANCE:0.9"
        )


def test_base_and_quote_must_differ():
    with pytest.raises(ValueError):
        Settings(
            CRYPTO_SCANNER_BASE_ASSET="BTC",
            CRYPTO_SCANNER_QUOTE_ASSET="BTC",
        )


def test_factory_builds_service_from_settings():
    config = Settings(
        CRYPTO_SCANNER_ENABLED=True,
        CRYPTO_SCANNER_VENUES="BINANCE,OKX,BYBIT",
    )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={})
        )
    )

    service = build_scanner_service(config, client=client)

    assert service.enabled is True
    assert sorted(service.sources) == [
        "BINANCE",
        "BYBIT",
        "OKX",
    ]
    assert service.pair.canonical == "BTC/USDT"
    assert len(service.scanner.fee_schedule) == 3

    asyncio.run(client.aclose())


def test_factory_refuses_unknown_venue():
    config = Settings(
        CRYPTO_SCANNER_VENUES="BINANCE,KRAKEN",
    )

    with pytest.raises(CryptoArbitrageError):
        build_scanner_service(config)


def test_factory_uses_each_venue_instrument_naming():
    config = Settings(
        CRYPTO_SCANNER_ENABLED=True,
        CRYPTO_SCANNER_VENUES="BINANCE,OKX",
    )

    client = httpx.AsyncClient(
        transport=httpx.MockTransport(
            lambda request: httpx.Response(200, json={})
        )
    )

    service = build_scanner_service(config, client=client)

    assert (
        service.scanner.fee_schedule.taker_rate(
            "OKX",
            "BTC-USDT",
        )
        == Decimal("0.001")
    )

    asyncio.run(client.aclose())
