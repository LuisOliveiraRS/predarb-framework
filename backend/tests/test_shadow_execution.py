from __future__ import annotations

import asyncio
from dataclasses import FrozenInstanceError

import pytest

from app.paper.shadow_execution_models import (
    ShadowExecutionRecord,
    ShadowFill,
    ShadowMarketReference,
    ShadowOrderIntent,
)
from app.paper.shadow_execution_repository import (
    ShadowExecutionAuditRepository,
)
from app.paper.shadow_execution_simulator import (
    ShadowExecutionSimulator,
)
from app.real_markets.models import (
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
)


def snapshot(
    *,
    connector_id,
    market_id,
    yes_ask,
    no_ask,
    yes_size=120.0,
    no_size=150.0,
):
    return MarketSnapshot(
        market=NormalizedMarket(
            connector_id=connector_id,
            market_id=market_id,
            title=(
                f"Mercado Shadow {market_id}"
            ),
            status="OPEN",
            outcomes=(
                MarketOutcome(
                    outcome_id=(
                        f"{market_id}-yes"
                    ),
                    label="YES",
                ),
                MarketOutcome(
                    outcome_id=(
                        f"{market_id}-no"
                    ),
                    label="NO",
                ),
            ),
            currency="USD",
        ),
        quotes=(
            MarketQuote(
                connector_id=connector_id,
                market_id=market_id,
                outcome_id=(
                    f"{market_id}-yes"
                ),
                bid=max(
                    0.0,
                    yes_ask - 0.01,
                ),
                ask=yes_ask,
                last=yes_ask,
                bid_size=yes_size,
                ask_size=yes_size,
            ),
            MarketQuote(
                connector_id=connector_id,
                market_id=market_id,
                outcome_id=(
                    f"{market_id}-no"
                ),
                bid=max(
                    0.0,
                    no_ask - 0.01,
                ),
                ask=no_ask,
                last=no_ask,
                bid_size=no_size,
                ask_size=no_size,
            ),
        ),
        source_latency_ms=1.0,
        raw_reference=(
            f"synthetic://{connector_id}/"
            f"{market_id}"
        ),
    )


def profitable_fixture():
    left = snapshot(
        connector_id="a",
        market_id="left",
        yes_ask=0.42,
        no_ask=0.58,
        yes_size=120.0,
        no_size=150.0,
    )

    right = snapshot(
        connector_id="b",
        market_id="right",
        yes_ask=0.46,
        no_ask=0.54,
        yes_size=120.0,
        no_size=150.0,
    )

    evaluation = {
        "match_id": "manual-shadow-match",
        "source": "MANUAL_CONFIRMED_MATCH",
        "manual_match_confirmed": True,
        "left_key": left.key,
        "right_key": right.key,
        "evaluated_at": (
            "2026-07-29T04:30:00+00:00"
        ),
        "status": "PROFITABLE",
        "reason_codes": [],
        "best_direction": {
            "status": "PROFITABLE",
            "direction": (
                "YES_LEFT__NO_RIGHT"
            ),
            "reason_codes": [],
            "legs": [
                {
                    "connector_id": "a",
                    "market_id": "left",
                    "outcome_id": (
                        "left-yes"
                    ),
                    "outcome_label": "YES",
                    "canonical_outcome": "YES",
                    "ask": 0.42,
                    "ask_size": 120.0,
                    "fee_rate": 0.001,
                    "slippage_bps": 10.0,
                },
                {
                    "connector_id": "b",
                    "market_id": "right",
                    "outcome_id": (
                        "right-no"
                    ),
                    "outcome_label": "NO",
                    "canonical_outcome": "NO",
                    "ask": 0.54,
                    "ask_size": 150.0,
                    "fee_rate": 0.002,
                    "slippage_bps": 20.0,
                },
            ],
            "simulated_quantity": 100.0,
            "raw_cost": 96.0,
            "fee_cost": 0.15,
            "slippage_cost": 0.15,
            "total_cost": 96.3,
            "simulated_payout": 100.0,
            "gross_profit": 4.0,
            "net_profit": 3.7,
            "gross_edge": 0.04,
            "net_edge": 0.037,
        },
        "economic_analysis_only": True,
        "shadow_only": True,
        "market_data_only": True,
        "read_only_market_access": True,
        "order_submission_available": False,
        "automatic_execution_authorized": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }

    return (
        left,
        right,
        evaluation,
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


def test_repository_blocks_unsafe_payload(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_audit.jsonl"
    )

    repository = (
        ShadowExecutionAuditRepository(
            path
        )
    )

    with pytest.raises(
        ValueError,
        match="financial_execution",
    ):
        repository.append(
            {
                "financial_execution": True,
            }
        )

    assert path.exists() is False
    assert repository.count() == 0


def test_repository_hash_chain_and_tamper_detection(
    tmp_path,
):
    path = (
        tmp_path
        / "shadow_audit.jsonl"
    )

    repository = (
        ShadowExecutionAuditRepository(
            path
        )
    )

    first = repository.append(
        {
            "name": "first_record",
            "financial_execution": False,
        }
    )

    second = repository.append(
        {
            "name": "second_record",
            "financial_execution": False,
        }
    )

    assert first["sequence"] == 1
    assert second["sequence"] == 2
    assert (
        second["previous_hash"]
        == first["record_hash"]
    )

    valid = repository.verify_integrity()

    assert valid["status"] == "VALID"
    assert valid["record_count"] == 2
    assert valid["errors"] == []

    content = path.read_text(
        encoding="utf-8"
    )

    path.write_text(
        content.replace(
            "first_record",
            "altered_record",
            1,
        ),
        encoding="utf-8",
    )

    invalid = repository.verify_integrity()

    assert invalid["status"] == "INVALID"
    assert any(
        item["error"]
        == "INVALID_RECORD_HASH"
        for item in invalid["errors"]
    )


def test_models_calculate_costs_and_are_immutable():
    market_snapshot = snapshot(
        connector_id="a",
        market_id="model",
        yes_ask=0.45,
        no_ask=0.55,
    )

    reference = (
        ShadowMarketReference
        .from_snapshot(
            market_snapshot,
            outcome_id="model-yes",
        )
    )

    order = ShadowOrderIntent(
        market=reference,
        side="BUY",
        quantity=100.0,
        requested_price=0.45,
        opportunity_id=(
            "shadow-model-test"
        ),
    )

    fill = ShadowFill(
        order_id=order.order_id,
        side="BUY",
        quantity=100.0,
        requested_price=0.45,
        fill_price=0.45,
        fee_rate=0.001,
        fee_basis_price=0.45,
        explicit_slippage_cost=0.09,
    )

    record = ShadowExecutionRecord(
        status="SIMULATED",
        market_references=(
            reference,
        ),
        orders=(
            order,
        ),
        fills=(
            fill,
        ),
        expected_payout=100.0,
    )

    assert order.requested_notional == 45.0
    assert fill.gross_notional == 45.0
    assert fill.fee == 0.045
    assert fill.slippage_cost == 0.09
    assert fill.cash_flow == -45.135
    assert (
        record.total_slippage_cost
        == 0.09
    )
    assert (
        record.simulated_profit
        == pytest.approx(
            54.865
        )
    )

    payload = record.to_audit_payload()

    assert (
        payload["financial_execution"]
        is False
    )
    assert (
        payload["live_execution"]
        is False
    )

    with pytest.raises(
        (
            FrozenInstanceError,
            AttributeError,
        )
    ):
        order.quantity = 1.0


def test_simulator_builds_profitable_record():
    (
        left,
        right,
        evaluation,
    ) = profitable_fixture()

    simulator = (
        ShadowExecutionSimulator()
    )

    record = simulator.build_record(
        evaluation=evaluation,
        snapshots={
            left.key: left,
            right.key: right,
        },
    )

    assert record.status == "SIMULATED"
    assert len(record.orders) == 2
    assert len(record.fills) == 2
    assert record.requested_notional == 96.0
    assert record.filled_notional == 96.0
    assert record.total_fees == 0.15
    assert (
        record.total_slippage_cost
        == 0.15
    )
    assert record.net_cash_flow == -96.3
    assert record.expected_payout == 100.0
    assert record.simulated_profit == 3.7
    assert all(
        item.side == "BUY"
        for item in record.orders
    )


def test_simulator_rejects_unconfirmed_match():
    (
        _,
        _,
        evaluation,
    ) = profitable_fixture()

    evaluation[
        "manual_match_confirmed"
    ] = False

    record = (
        ShadowExecutionSimulator()
        .build_record(
            evaluation=evaluation,
            snapshots={},
        )
    )

    assert record.status == "REJECTED"
    assert (
        "MANUAL_MATCH_NOT_CONFIRMED"
        in record.rejection_reasons
    )
    assert record.orders == ()
    assert record.fills == ()


def test_simulator_blocks_unsafe_evaluation():
    (
        left,
        right,
        evaluation,
    ) = profitable_fixture()

    evaluation[
        "financial_execution"
    ] = True

    with pytest.raises(
        ValueError,
        match="financial_execution",
    ):
        (
            ShadowExecutionSimulator()
            .build_record(
                evaluation=evaluation,
                snapshots={
                    left.key: left,
                    right.key: right,
                },
            )
        )


def test_simulator_blocks_snapshot_price_divergence():
    (
        left,
        right,
        evaluation,
    ) = profitable_fixture()

    evaluation[
        "best_direction"
    ] = dict(
        evaluation[
            "best_direction"
        ]
    )

    evaluation[
        "best_direction"
    ]["legs"] = [
        dict(item)
        for item in evaluation[
            "best_direction"
        ]["legs"]
    ]

    evaluation[
        "best_direction"
    ]["legs"][0]["ask"] = 0.43

    with pytest.raises(
        ValueError,
        match="ask do snapshot diverge",
    ):
        (
            ShadowExecutionSimulator()
            .build_record(
                evaluation=evaluation,
                snapshots={
                    left.key: left,
                    right.key: right,
                },
            )
        )


def test_async_simulation_persists_only_to_supplied_repository(
    tmp_path,
):
    (
        left,
        right,
        evaluation,
    ) = profitable_fixture()

    path = (
        tmp_path
        / "shadow_integration.jsonl"
    )

    repository = (
        ShadowExecutionAuditRepository(
            path
        )
    )

    market_service = MarketDataStub(
        [
            left,
            right,
        ]
    )

    simulator = ShadowExecutionSimulator(
        market_data_service=(
            market_service
        ),
        audit_repository=repository,
    )

    result = asyncio.run(
        simulator.simulate_evaluation(
            evaluation=evaluation,
            force_refresh=True,
            persist=True,
        )
    )

    assert result["status"] == "SIMULATED"
    assert result["persisted"] is True
    assert result["audit"]["sequence"] == 1
    assert (
        result["audit"]["event_type"]
        == "SHADOW_EXECUTION"
    )

    assert path.exists() is True
    assert repository.count() == 1
    assert (
        repository.verify_integrity()[
            "status"
        ]
        == "VALID"
    )

    assert len(market_service.calls) == 2
    assert all(
        force_refresh is True
        for _, force_refresh
        in market_service.calls
    )

    status = simulator.status()

    assert status["simulation_count"] == 1
    assert status["persisted_count"] == 1
    assert status["rejected_count"] == 0
    assert (
        status[
            "order_submission_available"
        ]
        is False
    )
    assert status["exchange_imports"] is False
    assert (
        status["financial_execution"]
        is False
    )
    assert (
        status["next_step_authorized"]
        is False
    )


def test_shadow_router_routes_are_read_only():
    from app.api.routers.shadow_execution import (
        router,
    )

    expected_paths = {
        (
            "/real-markets/"
            "shadow-execution/health"
        ),
        (
            "/real-markets/"
            "shadow-execution/status"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/status"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/integrity"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/records"
        ),
        (
            "/real-markets/"
            "shadow-execution/architecture"
        ),
    }

    found_paths = {
        route.path
        for route in router.routes
    }

    assert found_paths == expected_paths

    assert all(
        set(route.methods or set())
        == {"GET"}
        for route in router.routes
    )


def test_shadow_query_endpoints_do_not_create_audit(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        shadow_execution
        as router_module,
    )

    repository = (
        ShadowExecutionAuditRepository(
            tmp_path
            / "shadow_router_test.jsonl"
        )
    )

    simulator = ShadowExecutionSimulator(
        audit_repository=repository,
    )

    monkeypatch.setattr(
        router_module,
        "shadow_execution_audit_repository",
        repository,
    )

    monkeypatch.setattr(
        router_module,
        "shadow_execution_simulator",
        simulator,
    )

    health = asyncio.run(
        router_module
        .shadow_execution_health()
    )

    status = asyncio.run(
        router_module
        .shadow_execution_status()
    )

    audit_status = asyncio.run(
        router_module
        .shadow_audit_status()
    )

    integrity = asyncio.run(
        router_module
        .shadow_audit_integrity()
    )

    records = asyncio.run(
        router_module
        .shadow_audit_records(
            limit=10,
            newest_first=True,
        )
    )

    architecture = asyncio.run(
        router_module
        .shadow_execution_architecture()
    )

    assert health["status"] == "healthy"
    assert health["phase"] == "9E"

    assert (
        status["simulator"]["status"]
        == "READY"
    )

    assert (
        audit_status["audit"]["exists"]
        is False
    )

    assert (
        integrity["integrity"]["status"]
        == "VALID"
    )

    assert (
        integrity["integrity"][
            "record_count"
        ]
        == 0
    )

    assert records["count"] == 0
    assert records["total_records"] == 0
    assert records["records"] == []

    assert (
        architecture[
            "simulation_endpoint_available"
        ]
        is False
    )

    assert (
        architecture[
            "audit_write_endpoint_available"
        ]
        is False
    )

    for payload in (
        health,
        status,
        audit_status,
        integrity,
        records,
        architecture,
    ):
        assert (
            payload[
                "order_submission_available"
            ]
            is False
        )

        assert (
            payload[
                "paper_execution_authorized"
            ]
            is False
        )

        assert (
            payload["live_authorization"]
            is False
        )

        assert (
            payload["execution_authorized"]
            is False
        )

        assert (
            payload["live_execution"]
            is False
        )

        assert (
            payload["financial_execution"]
            is False
        )

        assert (
            payload["next_step_authorized"]
            is False
        )

    assert repository.path.exists() is False


def test_application_registers_phase9e_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
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
            "/real-markets/"
            "shadow-execution/health"
        ),
        (
            "/real-markets/"
            "shadow-execution/status"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/status"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/integrity"
        ),
        (
            "/real-markets/"
            "shadow-execution/audit/records"
        ),
        (
            "/real-markets/"
            "shadow-execution/architecture"
        ),
    }

    assert not (
        required - paths
    )

    shadow_routes = [
        context.original_route
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if (
            isinstance(
                context.original_route,
                APIRoute,
            )
            and context.path
            in required
        )
    ]

    assert len(shadow_routes) == 6

    assert all(
        set(route.methods or set())
        == {"GET"}
        for route in shadow_routes
    )
