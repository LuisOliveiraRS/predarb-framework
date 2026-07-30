import asyncio
from types import SimpleNamespace

from app.real_markets.opportunity_radar import (
    RadarConfiguration,
    RealOpportunityRadar,
)


class FakeConnector:
    connector_id = "fake"

    async def list_markets(self, *, limit=100):
        return [
            SimpleNamespace(
                market_id="market-1",
                title="Test market",
                source_url="https://example.test",
                close_time=None,
            )
        ]

    async def get_snapshot(self, market_id):
        return SimpleNamespace(
            quotes=(
                SimpleNamespace(
                    outcome_id="YES",
                    ask=0.46,
                ),
                SimpleNamespace(
                    outcome_id="NO",
                    ask=0.48,
                ),
            )
        )


def test_profitable_market_is_detected():
    radar = RealOpportunityRadar(
        connectors=[FakeConnector()]
    )

    payload = asyncio.run(
        radar.scan(
            RadarConfiguration(
                fee_buffer=0.02,
            )
        )
    )

    assert payload["markets_priced"] == 1
    assert payload["profitable_count"] == 1
    assert payload["profitable"][0]["total_cost"] == 0.94
    assert payload["profitable"][0][
        "conservative_edge"
    ] == 0.04
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False
