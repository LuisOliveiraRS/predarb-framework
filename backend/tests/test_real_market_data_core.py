from __future__ import annotations

import asyncio

import pytest

from app.real_markets.connectors import (
    MockReadOnlyPredictionConnector,
    ReadOnlyMarketConnector,
)
from app.real_markets.models import (
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
)
from app.real_markets.registry import (
    RealMarketConnectorRegistry,
)
from app.real_markets.service import (
    RealMarketDataService,
)


def test_market_quote_computes_spread_and_midpoint():
    quote = MarketQuote(
        connector_id="connector",
        market_id="market",
        outcome_id="YES",
        bid=0.40,
        ask=0.46,
        last=0.43,
        bid_size=100,
        ask_size=90,
    )

    assert quote.spread == 0.06
    assert quote.midpoint == 0.43


def test_market_quote_rejects_invalid_probability():
    with pytest.raises(
        ValueError,
        match="entre 0 e 1",
    ):
        MarketQuote(
            connector_id="connector",
            market_id="market",
            outcome_id="YES",
            bid=1.10,
            ask=None,
        )


def test_normalized_market_requires_unique_outcomes():
    with pytest.raises(
        ValueError,
        match="duplicado",
    ):
        NormalizedMarket(
            connector_id="connector",
            market_id="market",
            title="Mercado",
            status="OPEN",
            outcomes=(
                MarketOutcome(
                    outcome_id="YES",
                    label="Sim",
                ),
                MarketOutcome(
                    outcome_id="YES",
                    label="Sim duplicado",
                ),
            ),
        )


class UnsafeConnector(
    ReadOnlyMarketConnector
):
    connector_id = "unsafe"
    name = "Unsafe"
    read_only = False

    async def health(self):
        raise NotImplementedError

    async def list_markets(
        self,
        *,
        limit=100,
    ):
        raise NotImplementedError

    async def get_snapshot(
        self,
        market_id,
    ):
        raise NotImplementedError


def test_registry_rejects_non_read_only_connector():
    registry = RealMarketConnectorRegistry()

    with pytest.raises(
        ValueError,
        match="somente leitura",
    ):
        registry.register(
            UnsafeConnector()
        )


def test_registry_rejects_duplicate_connector():
    registry = RealMarketConnectorRegistry()
    connector = (
        MockReadOnlyPredictionConnector()
    )

    registry.register(connector)

    with pytest.raises(
        ValueError,
        match="já registrado",
    ):
        registry.register(connector)


def test_mock_connector_lists_markets_and_snapshot():
    async def scenario():
        connector = (
            MockReadOnlyPredictionConnector()
        )

        markets = await connector.list_markets(
            limit=10
        )

        snapshot = await connector.get_snapshot(
            markets[0].market_id
        )

        return markets, snapshot

    markets, snapshot = asyncio.run(
        scenario()
    )

    assert len(markets) == 2
    assert (
        snapshot.market.connector_id
        == "mock-real-market"
    )
    assert len(snapshot.quotes) == 2


def test_snapshot_rejects_unknown_outcome():
    market = NormalizedMarket(
        connector_id="connector",
        market_id="market",
        title="Mercado",
        status="OPEN",
        outcomes=(
            MarketOutcome(
                outcome_id="YES",
                label="Sim",
            ),
            MarketOutcome(
                outcome_id="NO",
                label="Não",
            ),
        ),
    )

    with pytest.raises(
        ValueError,
        match="inexistentes",
    ):
        MarketSnapshot(
            market=market,
            quotes=(
                MarketQuote(
                    connector_id="connector",
                    market_id="market",
                    outcome_id="OTHER",
                    bid=0.1,
                    ask=0.2,
                ),
            ),
        )


def test_service_lists_markets_and_uses_cache():
    async def scenario():
        registry = (
            RealMarketConnectorRegistry()
        )

        registry.register(
            MockReadOnlyPredictionConnector()
        )

        service = RealMarketDataService(
            registry=registry,
            cache_ttl_seconds=30,
        )

        markets = await service.list_markets(
            limit=10
        )

        first = await service.get_snapshot(
            connector_id=(
                markets[0].connector_id
            ),
            market_id=(
                markets[0].market_id
            ),
        )

        second = await service.get_snapshot(
            connector_id=(
                markets[0].connector_id
            ),
            market_id=(
                markets[0].market_id
            ),
        )

        return markets, first, second, service

    (
        markets,
        first,
        second,
        service,
    ) = asyncio.run(
        scenario()
    )

    assert len(markets) == 2
    assert first is second
    assert len(
        service.latest_snapshots()
    ) == 1


def test_manual_refresh_is_market_data_only():
    async def scenario():
        registry = (
            RealMarketConnectorRegistry()
        )

        registry.register(
            MockReadOnlyPredictionConnector()
        )

        service = RealMarketDataService(
            registry=registry,
        )

        return await service.refresh(
            limit=10
        )

    payload = asyncio.run(
        scenario()
    )

    assert payload["status"] == "SUCCESS"
    assert payload["captured_snapshots"] == 2
    assert payload["market_data_only"] is True
    assert payload["live_execution"] is False
    assert (
        payload["financial_execution"]
        is False
    )
    assert (
        payload["next_step_authorized"]
        is False
    )


def test_dashboard_contains_complete_refresh_token():
    from app.api.routers import (
        real_market_data
        as router_module,
    )

    response = asyncio.run(
        router_module
        .real_market_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Núcleo de Dados de Mercado"
        in body
    )
    assert (
        "REFRESH-REAL-MARKET-DATA"
        in body
    )
    assert (
        "Nenhum conector pode enviar ordens"
        in body
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_refresh_endpoint_requires_confirmation():
    from fastapi import HTTPException
    from app.api.routers import (
        real_market_data
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        asyncio.run(
            router_module.real_market_refresh(
                confirm="INVALID",
                connector_id=None,
                limit=50,
            )
        )

    assert exc.value.status_code == 400


def test_application_registers_phase9a_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.real_market_data import (
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
        "/real-markets/health",
        "/real-markets/connectors",
        "/real-markets/markets",
        (
            "/real-markets/markets/"
            "{connector_id}/{market_id}"
        ),
        "/real-markets/snapshots/latest",
        "/real-markets/refresh",
        "/real-markets/dashboard",
        "/real-markets/architecture",
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

    assert methods[
        "/real-markets/refresh"
    ] == {"POST"}

    for path, method_set in methods.items():
        if path != "/real-markets/refresh":
            assert method_set == {"GET"}
