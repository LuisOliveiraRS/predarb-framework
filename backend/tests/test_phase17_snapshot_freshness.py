import asyncio

import pytest

from app.api.routers import (
    real_opportunity_radar,
)
from app.core.settings import Settings
from app.core.settings import settings
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    RealOpportunityScanService,
)


class FakeMonitor:
    def __init__(self):
        self.count = 0

    async def scan(self, configuration):
        self.count += 1

        return {
            "status": "READY",
            "markets_priced": 1,
            "best_markets": [],
            "monitoring": {},
            "market_data_only": True,
            "read_only": True,
            "automatic_execution_authorized": False,
            "execution_authorized": False,
            "financial_execution": False,
            "order_submission_available": False,
        }


class FakeClock:
    def __init__(self):
        self.value = 0.0

    def __call__(self):
        return self.value

    def advance(self, seconds):
        self.value += seconds


def build_service(clock):
    return RealOpportunityScanService(
        monitor=FakeMonitor(),
        cache_ttl_seconds=45,
        clock=clock,
    )


def collect(service, configuration):
    return asyncio.run(
        service.scan(
            configuration,
            force_refresh=True,
        )
    )


def test_fresh_snapshot_is_not_stale():
    clock = FakeClock()
    service = build_service(clock)
    configuration = RadarConfiguration()

    collect(service, configuration)
    clock.advance(10.0)

    snapshot = service.latest_snapshot(configuration)

    assert snapshot["status"] == "READY"
    assert (
        snapshot["monitoring"]["snapshot_is_stale"]
        is False
    )
    assert (
        snapshot["monitoring"][
            "snapshot_configuration_match"
        ]
        is True
    )
    assert (
        snapshot["monitoring"]["snapshot_age_seconds"]
        == 10.0
    )


def test_old_snapshot_is_flagged_as_stale():
    clock = FakeClock()
    service = build_service(clock)
    configuration = RadarConfiguration()

    collect(service, configuration)

    max_age = service._snapshot_max_age_seconds()
    clock.advance(max_age + 1.0)

    snapshot = service.latest_snapshot(configuration)

    assert snapshot["status"] == "STALE"
    assert (
        snapshot["monitoring"]["snapshot_is_stale"]
        is True
    )
    assert (
        snapshot["monitoring"]["collected_status"]
        == "READY"
    )
    assert (
        snapshot["monitoring"][
            "snapshot_max_age_seconds"
        ]
        == max_age
    )
    assert snapshot["read_only"] is True
    assert snapshot["financial_execution"] is False


def test_stale_threshold_follows_collector_interval(
    monkeypatch,
):
    clock = FakeClock()
    service = build_service(clock)

    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_COLLECTOR_ENABLED",
        True,
    )
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_INTERVAL_SECONDS",
        60,
    )
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER",
        3,
    )

    assert (
        service._snapshot_max_age_seconds()
        == 180.0
    )


def test_snapshot_reports_configuration_mismatch():
    clock = FakeClock()
    service = build_service(clock)

    collected = RadarConfiguration(
        limit_per_connector=20,
    )
    requested = RadarConfiguration(
        limit_per_connector=40,
    )

    collect(service, collected)

    snapshot = service.latest_snapshot(requested)

    monitoring = snapshot["monitoring"]

    assert (
        snapshot["status"]
        == "CONFIGURATION_MISMATCH"
    )
    assert (
        monitoring["snapshot_configuration_match"]
        is False
    )
    assert (
        monitoring["snapshot_configuration"][
            "limit_per_connector"
        ]
        == 20
    )
    assert (
        monitoring["requested_configuration"][
            "limit_per_connector"
        ]
        == 40
    )


def test_stale_has_priority_over_mismatch():
    clock = FakeClock()
    service = build_service(clock)

    collect(
        service,
        RadarConfiguration(limit_per_connector=20),
    )

    clock.advance(
        service._snapshot_max_age_seconds() + 1.0
    )

    snapshot = service.latest_snapshot(
        RadarConfiguration(limit_per_connector=40)
    )

    assert snapshot["status"] == "STALE"
    assert (
        snapshot["monitoring"][
            "snapshot_configuration_match"
        ]
        is False
    )


def test_warming_up_snapshot_declares_no_data():
    clock = FakeClock()
    service = build_service(clock)

    snapshot = service.latest_snapshot(
        RadarConfiguration()
    )

    monitoring = snapshot["monitoring"]

    assert snapshot["status"] == "WARMING_UP"
    assert monitoring["snapshot_available"] is False
    assert monitoring["snapshot_is_stale"] is False


def test_snapshot_endpoint_defaults_to_collector_config(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR",
        35,
    )
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_FEE_BUFFER",
        0.03,
    )
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_NEAR_THRESHOLD",
        0.07,
    )
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_CONCURRENCY",
        6,
    )

    configuration = (
        real_opportunity_radar._snapshot_configuration(
            None,
            None,
            None,
        )
    )

    assert configuration.limit_per_connector == 35
    assert configuration.fee_buffer == 0.03
    assert configuration.near_threshold == 0.07
    assert configuration.concurrency == 6


def test_snapshot_endpoint_matches_collector_key(
    monkeypatch,
):
    """
    O dashboard nao envia parametros. A chave pedida
    precisa ser identica a chave produzida pelo coletor
    mesmo apos mudanca de ambiente no Render.
    """

    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_BACKGROUND_LIMIT_PER_CONNECTOR",
        35,
    )

    clock = FakeClock()
    service = build_service(clock)

    from app.real_markets.opportunity_background_collector import (  # noqa: E501
        real_opportunity_background_collector,
    )

    collect(
        service,
        real_opportunity_background_collector
        .configuration(),
    )

    monkeypatch.setattr(
        real_opportunity_radar,
        "real_opportunity_scan_service",
        service,
    )

    snapshot = asyncio.run(
        real_opportunity_radar.radar_snapshot(
            limit_per_connector=None,
            fee_buffer=None,
            near_threshold=None,
        )
    )

    assert snapshot["status"] == "READY"
    assert (
        snapshot["monitoring"][
            "snapshot_configuration_match"
        ]
        is True
    )


def test_snapshot_max_age_multiplier_is_validated():
    with pytest.raises(
        ValueError,
        match="SNAPSHOT_MAX_AGE_MULTIPLIER",
    ):
        Settings(
            _env_file=None,
            REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER=0,
        )

    with pytest.raises(
        ValueError,
        match="SNAPSHOT_MAX_AGE_MULTIPLIER",
    ):
        Settings(
            _env_file=None,
            REAL_OPPORTUNITY_SNAPSHOT_MAX_AGE_MULTIPLIER=11,
        )
