from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.real_markets.economics import (
    EconomicModelConfiguration,
    EconomicOpportunityEngine,
)
from app.real_markets.matching import (
    ManualMarketMatchStore,
)
from app.real_markets.models import (
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
)


def configuration(
    *,
    max_age=90,
    max_quantity="1000",
    min_edge="0.0025",
    min_profit="0.01",
    fee_a="0",
    fee_b="0",
    slippage_a="0",
    slippage_b="0",
):
    return EconomicModelConfiguration(
        max_snapshot_age_seconds=max_age,
        max_simulated_quantity=Decimal(
            max_quantity
        ),
        min_net_edge=Decimal(
            min_edge
        ),
        min_net_profit=Decimal(
            min_profit
        ),
        fee_rates={
            "default": Decimal("0"),
            "a": Decimal(fee_a),
            "b": Decimal(fee_b),
        },
        slippage_bps={
            "default": Decimal("0"),
            "a": Decimal(slippage_a),
            "b": Decimal(slippage_b),
        },
        currency_groups={
            "USD": "USD_STABLE",
            "PUSD": "USD_STABLE",
        },
    )


def snapshot(
    *,
    connector_id,
    market_id,
    yes_ask,
    no_ask,
    yes_size=100,
    no_size=100,
    currency="USD",
    captured_at=None,
):
    market = NormalizedMarket(
        connector_id=connector_id,
        market_id=market_id,
        title=(
            f"Mercado {market_id}"
        ),
        status="OPEN",
        outcomes=(
            MarketOutcome(
                outcome_id="YES",
                label="Yes",
                token_id=(
                    f"{market_id}-yes"
                ),
            ),
            MarketOutcome(
                outcome_id="NO",
                label="No",
                token_id=(
                    f"{market_id}-no"
                ),
            ),
        ),
        close_time=(
            "2026-12-31T23:59:59+00:00"
        ),
        currency=currency,
        category="test",
    )

    return MarketSnapshot(
        market=market,
        quotes=(
            MarketQuote(
                connector_id=connector_id,
                market_id=market_id,
                outcome_id="YES",
                bid=(
                    None
                    if yes_ask is None
                    else max(
                        0,
                        yes_ask - 0.01,
                    )
                ),
                ask=yes_ask,
                last=yes_ask,
                bid_size=yes_size,
                ask_size=yes_size,
            ),
            MarketQuote(
                connector_id=connector_id,
                market_id=market_id,
                outcome_id="NO",
                bid=(
                    None
                    if no_ask is None
                    else max(
                        0,
                        no_ask - 0.01,
                    )
                ),
                ask=no_ask,
                last=no_ask,
                bid_size=no_size,
                ask_size=no_size,
            ),
        ),
        captured_at=(
            captured_at
            or datetime.now(
                timezone.utc
            ).isoformat()
        ),
        source_latency_ms=1,
    )


class MarketDataStub:
    def __init__(
        self,
        snapshots,
    ):
        self.snapshots = {
            item.key: item
            for item in snapshots
        }
        self.calls = []

    async def get_snapshot(
        self,
        *,
        connector_id,
        market_id,
        force_refresh=False,
    ):
        key = (
            f"{connector_id}:"
            f"{market_id}"
        )

        self.calls.append(
            (
                key,
                force_refresh,
            )
        )

        if key not in self.snapshots:
            raise KeyError(key)

        return self.snapshots[key]


def engine(
    tmp_path,
    snapshots,
    *,
    config=None,
):
    return EconomicOpportunityEngine(
        market_data_service=(
            MarketDataStub(
                snapshots
            )
        ),
        match_store=(
            ManualMarketMatchStore(
                tmp_path
                / "matches.json"
            )
        ),
        configuration=(
            config
            or configuration()
        ),
    )


def test_profitable_direction_is_detected(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.40,
                no_ask=0.61,
                yes_size=50,
                no_size=50,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.62,
                no_ask=0.50,
                yes_size=40,
                no_size=40,
            ),
        ],
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    assert payload["status"] == "PROFITABLE"
    assert (
        payload["manual_match_confirmed"]
        is False
    )

    best = payload[
        "best_direction"
    ]

    assert (
        best["direction"]
        == "YES_LEFT__NO_RIGHT"
    )
    assert (
        best["simulated_quantity"]
        == 40
    )
    assert best["raw_cost"] == 36
    assert best["net_profit"] == 4
    assert best["net_edge"] == 0.1
    assert payload["live_execution"] is False


def test_fees_and_slippage_can_remove_profitability(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.49,
                no_ask=0.51,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.51,
                no_ask=0.49,
            ),
        ],
        config=configuration(
            min_edge="0.001",
            fee_a="0.02",
            fee_b="0.02",
            slippage_a="100",
            slippage_b="100",
        ),
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    assert (
        payload["status"]
        == "NOT_PROFITABLE"
    )
    assert all(
        item["net_profit"] < 0
        for item in payload[
            "directions"
        ]
    )


def test_liquidity_and_config_cap_quantity(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.30,
                no_ask=0.70,
                yes_size=500,
                no_size=500,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.70,
                no_ask=0.40,
                yes_size=12,
                no_size=12,
            ),
        ],
        config=configuration(
            max_quantity="10"
        ),
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    assert (
        payload["best_direction"][
            "simulated_quantity"
        ]
        == 10
    )


def test_stale_snapshot_is_rejected(
    tmp_path,
):
    old = (
        datetime.now(timezone.utc)
        - timedelta(seconds=120)
    ).isoformat()

    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.40,
                no_ask=0.60,
                captured_at=old,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.60,
                no_ask=0.40,
            ),
        ],
        config=configuration(
            max_age=30
        ),
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    assert payload["status"] == "REJECTED"
    assert (
        "LEFT_SNAPSHOT_STALE"
        in payload["reason_codes"]
    )


def test_currency_group_mismatch_is_rejected(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.40,
                no_ask=0.60,
                currency="USD",
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.60,
                no_ask=0.40,
                currency="EUR",
            ),
        ],
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    assert payload["status"] == "REJECTED"
    assert (
        "CURRENCY_GROUP_MISMATCH"
        in payload["reason_codes"]
    )


def test_missing_ask_rejects_only_affected_direction(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=None,
                no_ask=0.40,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.40,
                no_ask=0.60,
            ),
        ],
    )

    payload = asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
        )
    )

    statuses = {
        item["direction"]: (
            item["status"]
        )
        for item in payload[
            "directions"
        ]
    }

    assert (
        statuses[
            "YES_LEFT__NO_RIGHT"
        ]
        == "REJECTED"
    )
    assert (
        statuses[
            "NO_LEFT__YES_RIGHT"
        ]
        in {
            "PROFITABLE",
            "NOT_PROFITABLE",
        }
    )


def test_no_confirmed_matches_is_safe(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [],
    )

    payload = asyncio.run(
        analysis
        .evaluate_confirmed_matches()
    )

    assert (
        payload["status"]
        == "NO_CONFIRMED_MATCHES"
    )
    assert payload["opportunities"] == []
    assert (
        payload[
            "order_submission_available"
        ]
        is False
    )
    assert (
        payload["next_step_authorized"]
        is False
    )


def test_confirmed_match_is_evaluated(
    tmp_path,
):
    left = snapshot(
        connector_id="a",
        market_id="one",
        yes_ask=0.40,
        no_ask=0.60,
    )

    right = snapshot(
        connector_id="b",
        market_id="two",
        yes_ask=0.60,
        no_ask=0.40,
    )

    analysis = engine(
        tmp_path,
        [
            left,
            right,
        ],
    )

    record = (
        analysis.match_store.add(
            left_key="a:one",
            right_key="b:two",
            score={
                "score": 1.0,
            },
        )
    )

    payload = asyncio.run(
        analysis.evaluate_match(
            match_id=record["id"]
        )
    )

    assert (
        payload[
            "manual_match_confirmed"
        ]
        is True
    )
    assert (
        payload["match_id"]
        == record["id"]
    )


def test_force_refresh_is_forwarded(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [
            snapshot(
                connector_id="a",
                market_id="one",
                yes_ask=0.40,
                no_ask=0.60,
            ),
            snapshot(
                connector_id="b",
                market_id="two",
                yes_ask=0.60,
                no_ask=0.40,
            ),
        ],
    )

    asyncio.run(
        analysis.evaluate_pair(
            left_key="a:one",
            right_key="b:two",
            source="UNCONFIRMED_PREVIEW",
            force_refresh=True,
        )
    )

    assert all(
        force_refresh is True
        for _, force_refresh in (
            analysis
            .market_data_service
            .calls
        )
    )


def test_health_exposes_safe_configuration(
    tmp_path,
):
    analysis = engine(
        tmp_path,
        [],
    )

    payload = analysis.health()

    assert payload["status"] == "healthy"
    assert (
        payload["supported_structure"]
        == "BINARY_YES_NO"
    )
    assert (
        payload["manual_match_required"]
        is True
    )
    assert (
        payload[
            "automatic_execution_authorized"
        ]
        is False
    )
    assert (
        payload["financial_execution"]
        is False
    )


def test_dashboard_is_explicitly_shadow_only():
    from app.api.routers import (
        economic_opportunities
        as router_module,
    )

    response = asyncio.run(
        router_module
        .economic_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Motor Econômico de Oportunidades"
        in body
    )
    assert "Shadow mode" in body
    assert (
        "Nenhuma ordem disponível"
        in body
    )
    assert (
        response.headers[
            "x-predarb-order-submission"
        ]
        == "false"
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_application_registers_phase9d_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.economic_opportunities import (
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
        "/real-markets/economics/health",
        (
            "/real-markets/economics/"
            "configuration"
        ),
        (
            "/real-markets/economics/"
            "opportunities"
        ),
        (
            "/real-markets/economics/"
            "matches/{match_id}"
        ),
        "/real-markets/economics/preview",
        "/real-markets/economics/dashboard",
        (
            "/real-markets/economics/"
            "architecture"
        ),
    }

    assert not (
        required - paths
    )

    assert all(
        set(route.methods or set())
        == {"GET"}
        for route in router.routes
    )
