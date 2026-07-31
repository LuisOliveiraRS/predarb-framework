import asyncio

from app.real_markets.opportunity_monitor import (
    RealOpportunityMonitor,
)


def radar_payload(
    *,
    gross_edge=-0.01,
):
    market = {
        "connector_id": "fake",
        "market_id": "market-1",
        "title": "Test market",
        "source_url": "https://example.test",
        "yes_ask": 0.49,
        "no_ask": 0.52,
        "total_cost": 1.0 - gross_edge,
        "gross_edge": gross_edge,
        "conservative_edge": (
            gross_edge - 0.02
        ),
        "status": "NEAR_OPPORTUNITY",
    }

    return {
        "status": "READY",
        "markets_priced": 1,
        "best_markets": [market],
        "monitoring_markets": [market],
        "market_data_only": True,
        "read_only": True,
        "execution_authorized": False,
        "financial_execution": False,
    }


class FakeRepository:
    def __init__(
        self,
        *,
        available=True,
    ):
        self.available = available
        self.persist_calls = 0

    def load_histories(
        self,
        market_keys,
        *,
        limit_per_market,
    ):
        if not self.available:
            return {
                "histories": {},
                "markets_requested": len(
                    market_keys
                ),
                "markets_loaded": 0,
                "persistence_available": False,
                "error": "DatabaseUnavailable",
            }

        return {
            "histories": {
                "fake:market-1": [{
                    "observed_at": (
                        "2026-07-31T00:00:00+00:00"
                    ),
                    "gross_edge": -0.03,
                    "conservative_edge": -0.05,
                    "total_cost": 1.03,
                    "status": "NEAR_OPPORTUNITY",
                }],
            },
            "markets_requested": len(market_keys),
            "markets_loaded": 1,
            "persistence_available": True,
            "error": None,
        }

    def persist_observations(
        self,
        observations,
        *,
        observed_at,
    ):
        self.persist_calls += 1

        if not self.available:
            return {
                "persisted": False,
                "attempted": len(observations),
                "inserted": 0,
                "skipped": 0,
                "error": "DatabaseUnavailable",
            }

        return {
            "persisted": True,
            "attempted": len(observations),
            "inserted": len(observations),
            "skipped": 0,
            "error": None,
        }

    def load_history(
        self,
        connector_id,
        market_id,
        *,
        limit,
    ):
        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "points": [{
                "observed_at": (
                    "2026-07-31T00:00:00+00:00"
                ),
                "gross_edge": -0.03,
                "conservative_edge": -0.05,
                "total_cost": 1.03,
                "status": "NEAR_OPPORTUNITY",
            }],
            "count": 1,
            "persistence_available": (
                self.available
            ),
            "error": None,
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


def test_persisted_history_restores_trend_after_restart():
    repository = FakeRepository()

    monitor = RealOpportunityMonitor(
        radar=None,
        repository=repository,
        persistence_enabled=True,
    )

    result = asyncio.run(
        monitor.record(
            radar_payload(
                gross_edge=-0.01,
            )
        )
    )

    market = result["best_markets"][0]

    assert market["is_new"] is False
    assert market["previous_gross_edge"] == -0.03
    assert market["edge_change"] == 0.02
    assert market["trend"] == "IMPROVING"
    assert market["history_points"] == 2

    assert result["persistence"]["enabled"] is True
    assert result["persistence"]["hydrated_markets"] == 1
    assert result["persistence"]["persisted"] is True
    assert result["persistence"]["inserted"] == 1
    assert repository.persist_calls == 1

    assert result["read_only"] is True
    assert result["execution_authorized"] is False
    assert result["financial_execution"] is False


def test_database_failure_does_not_break_radar():
    repository = FakeRepository(
        available=False,
    )

    monitor = RealOpportunityMonitor(
        radar=None,
        repository=repository,
        persistence_enabled=True,
    )

    result = asyncio.run(
        monitor.record(
            radar_payload()
        )
    )

    market = result["best_markets"][0]

    assert market["is_new"] is True
    assert market["trend"] == "NEW"

    assert result["status"] == "READY"
    assert result["persistence"]["enabled"] is True
    assert result["persistence"]["available"] is False
    assert result["persistence"]["persisted"] is False
    assert result["persistence"]["error"] == (
        "DatabaseUnavailable"
    )

    assert result["read_only"] is True
    assert result["execution_authorized"] is False
    assert result["financial_execution"] is False
    assert (
        result["order_submission_available"]
        is False
    )


def test_history_prefers_persistent_repository():
    repository = FakeRepository()

    monitor = RealOpportunityMonitor(
        radar=None,
        repository=repository,
        persistence_enabled=True,
    )

    history = asyncio.run(
        monitor.get_history(
            "fake",
            "market-1",
            limit=10,
        )
    )

    assert history["source"] == "persistent"
    assert history["count"] == 1
    assert history["points"][0][
        "gross_edge"
    ] == -0.03
    assert history["read_only"] is True
    assert history["financial_execution"] is False
