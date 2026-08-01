import asyncio
from pathlib import Path

from app.api.routers import (
    real_opportunity_radar,
)


class FakeSnapshotService:
    def __init__(self):
        self.configuration = None
        self.scan_calls = 0

    def latest_snapshot(
        self,
        configuration,
    ):
        self.configuration = configuration

        return {
            "status": "READY",
            "best_markets": [],
            "monitoring": {
                "snapshot_available": True,
                "served_from_snapshot": True,
            },
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }

    async def scan(self, *args, **kwargs):
        self.scan_calls += 1

        raise AssertionError(
            "O endpoint snapshot nao deve coletar."
        )


def test_dashboard_uses_background_snapshot():
    source = Path(
        "app/dashboard/static/js/dashboard.js"
    ).read_text(
        encoding="utf-8",
    )

    assert (
        '"/real-markets/radar/snapshot"'
        in source
    )

    assert (
        '"/real-markets/radar/opportunities"'
        not in source
    )

    assert (
        "limit_per_connector"
        not in source
    )

    assert (
        "realRadarSnapshotWarnings"
        in source
    )


def test_snapshot_endpoint_does_not_scan(
    monkeypatch,
):
    service = FakeSnapshotService()

    monkeypatch.setattr(
        real_opportunity_radar,
        "real_opportunity_scan_service",
        service,
    )

    payload = asyncio.run(
        real_opportunity_radar.radar_snapshot(
            limit_per_connector=20,
            fee_buffer=0.02,
            near_threshold=0.05,
        )
    )

    assert service.scan_calls == 0
    assert (
        service.configuration
        .limit_per_connector
        == 20
    )
    assert (
        service.configuration.fee_buffer
        == 0.02
    )
    assert (
        service.configuration.near_threshold
        == 0.05
    )

    assert payload["status"] == "READY"
    assert (
        payload["monitoring"][
            "served_from_snapshot"
        ]
        is True
    )
    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert (
        payload["order_submission_available"]
        is False
    )
