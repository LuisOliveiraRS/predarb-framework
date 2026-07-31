import asyncio
from datetime import datetime, timezone

from app.real_markets.opportunity_monitor import (
    RealOpportunityMonitor,
)


def radar_payload(
    *,
    gross_edge,
    conservative_edge,
    status,
):
    return {
        "status": "READY",
        "best_markets": [{
            "connector_id": "fake",
            "market_id": "market-1",
            "title": "Test market",
            "gross_edge": gross_edge,
            "conservative_edge": conservative_edge,
            "total_cost": 1.0 - gross_edge,
            "status": status,
        }],
        "market_data_only": True,
        "read_only": True,
        "execution_authorized": False,
        "financial_execution": False,
    }


def test_monitor_tracks_edge_changes_and_profitability():
    monitor = RealOpportunityMonitor(
        radar=None,
        max_points_per_market=10,
    )

    first = asyncio.run(
        monitor.record(
            radar_payload(
                gross_edge=-0.02,
                conservative_edge=-0.04,
                status="NEAR_OPPORTUNITY",
            ),
            observed_at=datetime(
                2026,
                7,
                30,
                20,
                0,
                tzinfo=timezone.utc,
            ),
        )
    )

    first_market = first["best_markets"][0]

    assert first_market["is_new"] is True
    assert first_market["trend"] == "NEW"
    assert first_market["edge_change"] is None
    assert first["monitoring"]["new_count"] == 1

    second = asyncio.run(
        monitor.record(
            radar_payload(
                gross_edge=-0.005,
                conservative_edge=-0.025,
                status="NEAR_OPPORTUNITY",
            )
        )
    )

    second_market = second["best_markets"][0]

    assert second_market["is_new"] is False
    assert second_market["trend"] == "IMPROVING"
    assert second_market["edge_change"] == 0.015
    assert second_market["history_points"] == 2

    third = asyncio.run(
        monitor.record(
            radar_payload(
                gross_edge=0.04,
                conservative_edge=0.02,
                status="PROFITABLE",
            )
        )
    )

    third_market = third["best_markets"][0]

    assert third_market["became_profitable"] is True
    assert third["monitoring"][
        "became_profitable_count"
    ] == 1
    assert third["alerts"][0][
        "type"
    ] == "BECAME_PROFITABLE"

    assert third["read_only"] is True
    assert third["execution_authorized"] is False
    assert third["financial_execution"] is False
    assert third["order_submission_available"] is False

    history = asyncio.run(
        monitor.get_history(
            "fake",
            "market-1",
        )
    )

    assert history["count"] == 3
    assert history["points"][-1]["status"] == "PROFITABLE"
    assert history["financial_execution"] is False


def test_monitor_limits_history_points():
    monitor = RealOpportunityMonitor(
        radar=None,
        max_points_per_market=2,
    )

    for edge in (-0.03, -0.02, -0.01):
        asyncio.run(
            monitor.record(
                radar_payload(
                    gross_edge=edge,
                    conservative_edge=edge - 0.02,
                    status="NEAR_OPPORTUNITY",
                )
            )
        )

    history = asyncio.run(
        monitor.get_history(
            "fake",
            "market-1",
        )
    )

    assert history["count"] == 2
    assert history["points"][0]["gross_edge"] == -0.02
    assert history["points"][1]["gross_edge"] == -0.01


def test_monitor_tracks_all_priced_markets_not_only_best():
    monitor = RealOpportunityMonitor(
        radar=None,
        max_points_per_market=10,
    )

    markets = [
        {
            "connector_id": "fake",
            "market_id": f"market-{index}",
            "title": f"Market {index}",
            "gross_edge": -0.01 * index,
            "conservative_edge": (
                -0.02 - (0.01 * index)
            ),
            "total_cost": 1.0 + (0.01 * index),
            "status": "NEAR_OPPORTUNITY",
        }
        for index in range(1, 4)
    ]

    payload = {
        "status": "READY",
        "markets_priced": 3,
        "best_markets": markets[:1],
        "monitoring_markets": markets,
        "market_data_only": True,
        "read_only": True,
        "execution_authorized": False,
        "financial_execution": False,
    }

    result = asyncio.run(
        monitor.record(payload)
    )

    assert result["monitoring"][
        "markets_observed"
    ] == 3
    assert result["monitoring"][
        "tracked_markets"
    ] == 3
    assert result["monitoring"][
        "new_count"
    ] == 3
    assert result["monitoring"][
        "history_points"
    ] == 3

    assert len(result["best_markets"]) == 1
    assert "monitoring_markets" not in result

    hidden_history = asyncio.run(
        monitor.get_history(
            "fake",
            "market-3",
        )
    )

    assert hidden_history["count"] == 1
    assert hidden_history["read_only"] is True
    assert hidden_history["financial_execution"
    ] is False
