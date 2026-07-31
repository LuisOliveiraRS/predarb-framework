import asyncio

from app.api.routers import real_opportunity_radar
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)


class FakeMonitor:
    def __init__(self):
        self.scan_configuration = None
        self.history_request = None

    async def scan(self, configuration):
        self.scan_configuration = configuration

        return {
            "status": "READY",
            "monitoring": {
                "tracked_markets": 1,
                "history_points": 1,
            },
            "alerts": [],
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }

    async def get_history(
        self,
        connector_id,
        market_id,
        *,
        limit,
    ):
        self.history_request = {
            "connector_id": connector_id,
            "market_id": market_id,
            "limit": limit,
        }

        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "count": 2,
            "points": [
                {
                    "gross_edge": -0.02,
                },
                {
                    "gross_edge": -0.01,
                },
            ],
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


def test_opportunities_endpoint_uses_monitor(monkeypatch):
    monitor = FakeMonitor()

    monkeypatch.setattr(
        real_opportunity_radar,
        "real_opportunity_monitor",
        monitor,
    )

    payload = asyncio.run(
        real_opportunity_radar.radar_opportunities(
            limit_per_connector=25,
            fee_buffer=0.03,
            near_threshold=0.06,
        )
    )

    configuration = monitor.scan_configuration

    assert isinstance(
        configuration,
        RadarConfiguration,
    )
    assert configuration.limit_per_connector == 25
    assert configuration.fee_buffer == 0.03
    assert configuration.near_threshold == 0.06

    assert payload["monitoring"][
        "tracked_markets"
    ] == 1
    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False


def test_history_endpoint_returns_read_only_points(
    monkeypatch,
):
    monitor = FakeMonitor()

    monkeypatch.setattr(
        real_opportunity_radar,
        "real_opportunity_monitor",
        monitor,
    )

    payload = asyncio.run(
        real_opportunity_radar.radar_market_history(
            connector_id="kalshi",
            market_id="market-123",
            limit=30,
        )
    )

    assert monitor.history_request == {
        "connector_id": "kalshi",
        "market_id": "market-123",
        "limit": 30,
    }

    assert payload["count"] == 2
    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False
