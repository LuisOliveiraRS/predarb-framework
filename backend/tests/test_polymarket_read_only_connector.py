from __future__ import annotations

import asyncio
import json

import httpx
import pytest

from app.real_markets.polymarket import (
    PolymarketReadOnlyConnector,
    build_polymarket_connector_from_env,
)


EVENTS_PAYLOAD = [
    {
        "id": "event-1",
        "slug": "bitcoin-above-100k",
        "title": "Bitcoin acima de US$ 100 mil?",
        "category": "crypto",
        "markets": [
            {
                "id": "market-1",
                "question": (
                    "Bitcoin ficará acima de "
                    "US$ 100 mil no fim de 2026?"
                ),
                "conditionId": "condition-1",
                "questionID": "question-1",
                "slug": "bitcoin-above-100k-market",
                "active": True,
                "closed": False,
                "acceptingOrders": True,
                "enableOrderBook": True,
                "negRisk": False,
                "endDate": (
                    "2026-12-31T23:59:59Z"
                ),
                "outcomes": json.dumps(
                    [
                        "Yes",
                        "No",
                    ]
                ),
                "clobTokenIds": json.dumps(
                    [
                        "token-yes",
                        "token-no",
                    ]
                ),
                "liquidity": "12500.5",
                "volume": "500000.25",
                "volume24hr": "9500.75",
            }
        ],
    }
]


MARKET_PAYLOAD = (
    EVENTS_PAYLOAD[0]["markets"][0]
)


def transport_handler(
    request: httpx.Request,
) -> httpx.Response:
    path = request.url.path

    if (
        request.url.host
        == "gamma-api.polymarket.com"
        and path == "/events"
    ):
        return httpx.Response(
            200,
            json=EVENTS_PAYLOAD,
        )

    if (
        request.url.host
        == "gamma-api.polymarket.com"
        and path == "/markets/market-1"
    ):
        return httpx.Response(
            200,
            json=MARKET_PAYLOAD,
        )

    if (
        request.url.host
        == "clob.polymarket.com"
        and path == "/ok"
    ):
        return httpx.Response(
            200,
            text="OK",
        )

    if (
        request.url.host
        == "clob.polymarket.com"
        and path == "/book"
    ):
        token_id = request.url.params.get(
            "token_id"
        )

        if token_id == "token-yes":
            return httpx.Response(
                200,
                json={
                    "market": "condition-1",
                    "asset_id": "token-yes",
                    "timestamp": "123",
                    "hash": "yes-hash",
                    "bids": [
                        {
                            "price": "0.60",
                            "size": "150",
                        },
                        {
                            "price": "0.62",
                            "size": "100",
                        },
                    ],
                    "asks": [
                        {
                            "price": "0.66",
                            "size": "80",
                        },
                        {
                            "price": "0.64",
                            "size": "120",
                        },
                    ],
                    "last_trade_price": "0.63",
                    "min_order_size": "1",
                    "tick_size": "0.01",
                    "neg_risk": False,
                },
            )

        if token_id == "token-no":
            return httpx.Response(
                200,
                json={
                    "market": "condition-1",
                    "asset_id": "token-no",
                    "timestamp": "123",
                    "hash": "no-hash",
                    "bids": [
                        {
                            "price": "0.34",
                            "size": "80",
                        },
                        {
                            "price": "0.35",
                            "size": "110",
                        },
                    ],
                    "asks": [
                        {
                            "price": "0.39",
                            "size": "100",
                        },
                        {
                            "price": "0.37",
                            "size": "130",
                        },
                    ],
                    "last_trade_price": "0.36",
                    "min_order_size": "1",
                    "tick_size": "0.01",
                    "neg_risk": False,
                },
            )

    return httpx.Response(
        404,
        json={
            "error": "not found",
        },
    )


def connector() -> PolymarketReadOnlyConnector:
    return PolymarketReadOnlyConnector(
        transport=httpx.MockTransport(
            transport_handler
        ),
        retry_base_seconds=0,
    )


def test_descriptor_is_strictly_read_only():
    payload = connector().descriptor()

    assert payload["connector_id"] == "polymarket"
    assert payload["read_only"] is True
    assert (
        payload["authentication_required"]
        is False
    )
    assert (
        payload["trading_endpoints_enabled"]
        is False
    )
    assert (
        "public_clob_orderbook"
        in payload["capabilities"]
    )


def test_list_markets_normalizes_gamma_event():
    markets = asyncio.run(
        connector().list_markets(
            limit=10
        )
    )

    assert len(markets) == 1

    market = markets[0]

    assert market.market_id == "market-1"
    assert market.status == "OPEN"
    assert market.currency == "pUSD"
    assert (
        market.source_url
        == (
            "https://polymarket.com/"
            "event/bitcoin-above-100k"
        )
    )
    assert [
        item.outcome_id
        for item in market.outcomes
    ] == [
        "YES",
        "NO",
    ]
    assert [
        item.token_id
        for item in market.outcomes
    ] == [
        "token-yes",
        "token-no",
    ]


def test_snapshot_uses_best_bid_and_ask():
    snapshot = asyncio.run(
        connector().get_snapshot(
            "market-1"
        )
    )

    quotes = {
        item.outcome_id: item
        for item in snapshot.quotes
    }

    assert quotes["YES"].bid == 0.62
    assert quotes["YES"].ask == 0.64
    assert quotes["YES"].bid_size == 100
    assert quotes["YES"].ask_size == 120
    assert quotes["YES"].last == 0.63
    assert quotes["YES"].spread == 0.02

    assert quotes["NO"].bid == 0.35
    assert quotes["NO"].ask == 0.37
    assert quotes["NO"].last == 0.36

    assert (
        snapshot.metadata[
            "authentication_required"
        ]
        is False
    )
    assert (
        snapshot.metadata[
            "trading_endpoints_enabled"
        ]
        is False
    )


def test_health_accepts_textual_clob_ok():
    health = asyncio.run(
        connector().health()
    )

    assert health.healthy is True
    assert (
        health.metadata[
            "gamma_reachable"
        ]
        is True
    )
    assert (
        health.metadata[
            "clob_reachable"
        ]
        is True
    )


def test_transient_failure_is_retried():
    attempts = {
        "events": 0,
    }

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        if request.url.path == "/events":
            attempts["events"] += 1

            if attempts["events"] == 1:
                return httpx.Response(
                    503,
                    json={
                        "error": "temporary",
                    },
                )

            return httpx.Response(
                200,
                json=EVENTS_PAYLOAD,
            )

        return transport_handler(request)

    test_connector = (
        PolymarketReadOnlyConnector(
            transport=httpx.MockTransport(
                handler
            ),
            max_retries=1,
            retry_base_seconds=0,
        )
    )

    markets = asyncio.run(
        test_connector.list_markets(
            limit=5
        )
    )

    assert len(markets) == 1
    assert attempts["events"] == 2


def test_insecure_base_url_is_rejected():
    with pytest.raises(
        ValueError,
        match="insegura",
    ):
        PolymarketReadOnlyConnector(
            gamma_base_url=(
                "http://gamma.example"
            ),
            clob_base_url=(
                "https://clob.example"
            ),
        )


def test_connector_can_be_disabled_by_env(
    monkeypatch,
):
    monkeypatch.setenv(
        "POLYMARKET_READ_ONLY_ENABLED",
        "false",
    )

    assert (
        build_polymarket_connector_from_env()
        is None
    )


def test_default_registry_contains_polymarket():
    from app.real_markets.service import (
        real_market_registry,
    )

    registered = (
        real_market_registry.get(
            "polymarket"
        )
    )

    assert (
        registered.connector_id
        == "polymarket"
    )
    assert registered.read_only is True


def test_configuration_and_architecture_are_safe():
    from app.api.routers import (
        polymarket_read_only
        as router_module,
    )

    configuration = asyncio.run(
        router_module
        .polymarket_configuration()
    )

    architecture = asyncio.run(
        router_module
        .polymarket_architecture()
    )

    for payload in (
        configuration,
        architecture,
    ):
        assert payload["market_data_only"] is True
        assert payload["read_only"] is True
        assert (
            payload["authentication_required"]
            is False
        )
        assert (
            payload["trading_endpoints_enabled"]
            is False
        )
        assert payload["live_execution"] is False
        assert (
            payload["financial_execution"]
            is False
        )
        assert (
            payload["next_step_authorized"]
            is False
        )

    assert (
        "order_creation"
        in architecture[
            "explicitly_excluded"
        ]
    )


def test_application_registers_phase9b_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.polymarket_read_only import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        (
            "/real-markets/polymarket/"
            "configuration"
        ),
        (
            "/real-markets/polymarket/"
            "health"
        ),
        (
            "/real-markets/polymarket/"
            "markets"
        ),
        (
            "/real-markets/polymarket/"
            "markets/{market_id}/snapshot"
        ),
        (
            "/real-markets/polymarket/"
            "architecture"
        ),
    }

    assert not (
        required - paths
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert all(
        method_set == {"GET"}
        for method_set in methods.values()
    )
