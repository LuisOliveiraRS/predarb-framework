import asyncio

from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    RealOpportunityScanService,
)


class FakeMonitor:
    def __init__(self):
        self.scan_count = 0
        self.history_requests = []

    async def scan(self, configuration):
        self.scan_count += 1
        await asyncio.sleep(0.02)

        return {
            "status": "READY",
            "markets_priced": 1,
            "best_markets": [],
            "monitoring": {
                "history_points": self.scan_count,
            },
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
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
        self.history_requests.append({
            "connector_id": connector_id,
            "market_id": market_id,
            "limit": limit,
        })

        return {
            "connector_id": connector_id,
            "market_id": market_id,
            "points": [],
            "count": 0,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


def test_concurrent_requests_share_one_scan():
    monitor = FakeMonitor()
    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
    )

    async def scenario():
        configuration = RadarConfiguration()

        return await asyncio.gather(
            service.scan(configuration),
            service.scan(configuration),
            service.scan(configuration),
            service.scan(configuration),
        )

    payloads = asyncio.run(scenario())

    assert monitor.scan_count == 1

    cache_hits = [
        payload["monitoring"]["cache_hit"]
        for payload in payloads
    ]

    assert cache_hits.count(False) == 1
    assert cache_hits.count(True) == 3

    for payload in payloads:
        assert payload["read_only"] is True
        assert (
            payload["execution_authorized"]
            is False
        )
        assert (
            payload["financial_execution"]
            is False
        )
        assert (
            payload["order_submission_available"]
            is False
        )


def test_cache_hit_does_not_create_new_observation():
    monitor = FakeMonitor()
    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
    )

    first = asyncio.run(
        service.scan(RadarConfiguration())
    )
    second = asyncio.run(
        service.scan(RadarConfiguration())
    )

    assert monitor.scan_count == 1
    assert first["monitoring"]["cache_hit"] is False
    assert second["monitoring"]["cache_hit"] is True
    assert (
        first["monitoring"]["history_points"]
        == second["monitoring"]["history_points"]
        == 1
    )


def test_force_refresh_creates_one_new_scan():
    monitor = FakeMonitor()
    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
    )

    asyncio.run(
        service.scan(RadarConfiguration())
    )

    refreshed = asyncio.run(
        service.scan(
            RadarConfiguration(),
            force_refresh=True,
        )
    )

    assert monitor.scan_count == 2
    assert (
        refreshed["monitoring"]["cache_hit"]
        is False
    )
    assert (
        refreshed["monitoring"]["history_points"]
        == 2
    )


def test_history_is_delegated_to_monitor():
    monitor = FakeMonitor()
    service = RealOpportunityScanService(
        monitor=monitor,
    )

    payload = asyncio.run(
        service.get_history(
            "kalshi",
            "market-123",
            limit=25,
        )
    )

    assert monitor.history_requests == [{
        "connector_id": "kalshi",
        "market_id": "market-123",
        "limit": 25,
    }]

    assert payload["read_only"] is True
    assert payload["financial_execution"] is False



def test_concurrent_force_refresh_requests_share_one_new_scan():
    monitor = FakeMonitor()
    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
    )

    async def scenario():
        configuration = RadarConfiguration()

        await service.scan(configuration)

        return await asyncio.gather(
            service.scan(
                configuration,
                force_refresh=True,
            ),
            service.scan(
                configuration,
                force_refresh=True,
            ),
            service.scan(
                configuration,
                force_refresh=True,
            ),
        )

    payloads = asyncio.run(scenario())

    assert monitor.scan_count == 2

    cache_hits = [
        payload["monitoring"]["cache_hit"]
        for payload in payloads
    ]

    assert cache_hits.count(False) == 1
    assert cache_hits.count(True) == 2

    for payload in payloads:
        assert payload["read_only"] is True
        assert payload["execution_authorized"] is False
        assert payload["financial_execution"] is False
        assert (
            payload["order_submission_available"]
            is False
        )
