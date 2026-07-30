import asyncio

import httpx

from app.real_markets.kalshi import (
    KalshiReadOnlyConnector,
)


def handler(request: httpx.Request) -> httpx.Response:
    market = {
        "ticker": "KXTEST",
        "event_ticker": "KXEVENT",
        "title": "Will the test happen?",
        "status": "open",
        "close_time": "2026-12-31T23:59:59Z",
        "last_price_dollars": "0.5400",
    }

    if request.url.path.endswith(
        "/markets/KXTEST/orderbook"
    ):
        return httpx.Response(
            200,
            json={
                "orderbook_fp": {
                    "yes_dollars": [
                        ["0.5000", "10.00"],
                    ],
                    "no_dollars": [
                        ["0.4400", "12.00"],
                    ],
                }
            },
        )

    if request.url.path.endswith(
        "/markets/KXTEST"
    ):
        return httpx.Response(
            200,
            json={"market": market},
        )

    return httpx.Response(
        200,
        json={
            "markets": [market],
            "cursor": "",
        },
    )


def connector():
    return KalshiReadOnlyConnector(
        base_url="https://example.test",
        transport=httpx.MockTransport(handler),
        max_retries=0,
    )


def test_kalshi_health_and_markets():
    current = connector()

    health = asyncio.run(current.health())
    markets = asyncio.run(
        current.list_markets(limit=10)
    )

    assert health.healthy is True
    assert health.read_only is True
    assert len(markets) == 1
    assert markets[0].connector_id == "kalshi"
    assert markets[0].market_id == "KXTEST"


def test_kalshi_snapshot_is_read_only():
    snapshot = asyncio.run(
        connector().get_snapshot("KXTEST")
    )

    yes, no = snapshot.quotes

    assert yes.bid == 0.5
    assert yes.ask == 0.56
    assert no.bid == 0.44
    assert no.ask == 0.5
    assert snapshot.metadata[
        "trading_endpoints_enabled"
    ] is False
    assert snapshot.metadata["read_only"] is True
