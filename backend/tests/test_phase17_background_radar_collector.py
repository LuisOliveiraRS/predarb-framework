import asyncio
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from threading import Lock

import pytest

from app.core.settings import Settings
from app.real_markets.opportunity_background_collector import (
    RealOpportunityBackgroundCollector,
)
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    RealOpportunityScanService,
)


class FakeMonitor:
    def __init__(self):
        self.count = 0
        self.lock = Lock()

    async def scan(self, configuration):
        with self.lock:
            self.count += 1
            count = self.count

        await asyncio.sleep(0.05)

        return {
            "status": "READY",
            "markets_priced": 2,
            "best_markets": [],
            "monitoring": {
                "history_points": count,
            },
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


def test_scan_single_flight_across_threads():
    monitor = FakeMonitor()

    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
    )

    configuration = RadarConfiguration()
    start_barrier = Barrier(4)

    def run(_):
        start_barrier.wait(timeout=3)

        return asyncio.run(
            service.scan(
                configuration,
                force_refresh=True,
            )
        )

    with ThreadPoolExecutor(
        max_workers=4
    ) as executor:
        payloads = list(
            executor.map(
                run,
                range(4),
            )
        )

    assert monitor.count == 1

    hits = [
        payload["monitoring"]["cache_hit"]
        for payload in payloads
    ]

    assert hits.count(False) == 1
    assert hits.count(True) == 3


def test_latest_snapshot_does_not_scan():
    monitor = FakeMonitor()

    service = RealOpportunityScanService(
        monitor=monitor,
    )

    asyncio.run(
        service.scan(
            RadarConfiguration(),
            force_refresh=True,
        )
    )

    snapshot = service.latest_snapshot(
        RadarConfiguration()
    )

    assert monitor.count == 1
    assert snapshot["status"] == "READY"
    assert (
        snapshot["monitoring"][
            "served_from_snapshot"
        ]
        is True
    )
    assert (
        snapshot["monitoring"][
            "snapshot_available"
        ]
        is True
    )


def test_snapshot_starts_in_warming_up():
    service = RealOpportunityScanService(
        monitor=FakeMonitor(),
    )

    snapshot = service.latest_snapshot()

    assert snapshot["status"] == "WARMING_UP"
    assert snapshot["best_markets"] == []
    assert snapshot["read_only"] is True
    assert snapshot["financial_execution"] is False


class FakeScanService:
    def __init__(self):
        self.calls = 0

    async def scan(
        self,
        configuration,
        *,
        force_refresh,
    ):
        self.calls += 1

        return {
            "status": "READY",
            "markets_priced": 3,
            "best_markets": [],
            "monitoring": {},
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


def test_background_collector_runs_cycle():
    service = FakeScanService()

    collector = RealOpportunityBackgroundCollector(
        scan_service=service,
        enabled=True,
    )

    result = asyncio.run(
        collector.run_cycle()
    )

    assert service.calls == 1
    assert result["status"] == "READY"
    assert result["successes"] == 1
    assert result["last_markets_priced"] == 3
    assert result["read_only"] is True
    assert result["financial_execution"] is False


def test_background_collector_disabled():
    service = FakeScanService()

    collector = RealOpportunityBackgroundCollector(
        scan_service=service,
        enabled=False,
    )

    result = asyncio.run(
        collector.run_cycle()
    )

    assert result["status"] == "DISABLED"
    assert service.calls == 0


def test_background_collector_requires_scheduler():
    with pytest.raises(
        ValueError,
        match="exige SCHEDULER_ENABLED",
    ):
        Settings(
            _env_file=None,
            SCHEDULER_ENABLED=False,
            REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED=True,
        )
