import asyncio

import pytest
from fastapi.testclient import TestClient

from app.api.routers import (
    real_opportunity_radar,
)
from app.auth.dependencies import (
    require_dashboard_user,
)
from app.core.application import create_app
from app.core.settings import Settings
from app.core.settings import settings
from app.real_markets.opportunity_radar import (
    RadarConfiguration,
)
from app.real_markets.opportunity_scan_service import (
    RealOpportunityScanService,
)


class CountingMonitor:
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


@pytest.fixture
def cooldown_service(monkeypatch):
    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS",
        30,
    )

    clock = FakeClock()
    monitor = CountingMonitor()

    service = RealOpportunityScanService(
        monitor=monitor,
        cache_ttl_seconds=45,
        clock=clock,
    )

    return service, monitor, clock


def force(service, bypass_cooldown=False):
    return asyncio.run(
        service.scan(
            RadarConfiguration(),
            force_refresh=True,
            bypass_cooldown=bypass_cooldown,
        )
    )


def test_first_force_refresh_is_applied(
    cooldown_service,
):
    service, monitor, _ = cooldown_service

    payload = force(service)

    assert monitor.count == 1
    assert (
        payload["monitoring"][
            "force_refresh_applied"
        ]
        is True
    )
    assert (
        payload["monitoring"][
            "force_refresh_retry_after_seconds"
        ]
        == 0.0
    )


def test_force_refresh_within_cooldown_is_downgraded(
    cooldown_service,
):
    service, monitor, clock = cooldown_service

    force(service)
    clock.advance(5.0)

    payload = force(service)

    assert monitor.count == 1

    monitoring = payload["monitoring"]

    assert monitoring["force_refresh_requested"] is True
    assert monitoring["force_refresh_applied"] is False
    assert (
        monitoring[
            "force_refresh_retry_after_seconds"
        ]
        == 25.0
    )
    assert monitoring["cache_hit"] is True


def test_force_refresh_released_after_cooldown(
    cooldown_service,
):
    service, monitor, clock = cooldown_service

    force(service)
    clock.advance(31.0)

    payload = force(service)

    assert monitor.count == 2
    assert (
        payload["monitoring"][
            "force_refresh_applied"
        ]
        is True
    )


def test_collector_bypass_ignores_cooldown(
    cooldown_service,
):
    service, monitor, clock = cooldown_service

    force(service)
    clock.advance(1.0)

    force(service, bypass_cooldown=True)

    assert monitor.count == 2


def test_cooldown_zero_disables_throttling(
    cooldown_service,
    monkeypatch,
):
    service, monitor, clock = cooldown_service

    monkeypatch.setattr(
        settings,
        "REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS",
        0,
    )

    force(service)
    clock.advance(1.0)
    force(service)

    assert monitor.count == 2


def test_cooldown_is_isolated_per_configuration(
    cooldown_service,
):
    service, monitor, clock = cooldown_service

    asyncio.run(
        service.scan(
            RadarConfiguration(limit_per_connector=20),
            force_refresh=True,
        )
    )

    clock.advance(1.0)

    asyncio.run(
        service.scan(
            RadarConfiguration(limit_per_connector=40),
            force_refresh=True,
        )
    )

    assert monitor.count == 2


def test_normal_scan_is_not_throttled(
    cooldown_service,
):
    service, monitor, clock = cooldown_service

    force(service)
    clock.advance(1.0)

    payload = asyncio.run(
        service.scan(RadarConfiguration())
    )

    assert monitor.count == 1
    assert (
        payload["monitoring"][
            "force_refresh_requested"
        ]
        is False
    )


def test_cooldown_setting_is_validated():
    with pytest.raises(
        ValueError,
        match="FORCE_REFRESH_COOLDOWN_SECONDS",
    ):
        Settings(
            _env_file=None,
            REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS=-1,
        )

    with pytest.raises(
        ValueError,
        match="FORCE_REFRESH_COOLDOWN_SECONDS",
    ):
        Settings(
            _env_file=None,
            REAL_OPPORTUNITY_FORCE_REFRESH_COOLDOWN_SECONDS=3601,
        )


def test_opportunities_requires_authentication(
    monkeypatch,
):
    """
    O unico endpoint do radar capaz de atingir os
    provedores upstream nao pode ficar aberto quando
    a autenticacao do dashboard esta exigida.
    """

    monkeypatch.setattr(
        settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    app = create_app()

    with TestClient(app) as client:
        response = client.get(
            "/real-markets/radar/opportunities",
        )

    assert response.status_code in (401, 403)


def test_snapshot_stays_public(
    monkeypatch,
):
    """
    Snapshot e status leem memoria e nao geram carga
    upstream, entao seguem publicos como antes.
    """

    monkeypatch.setattr(
        settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    app = create_app()

    with TestClient(app) as client:
        snapshot = client.get(
            "/real-markets/radar/snapshot",
        )
        status = client.get(
            "/real-markets/radar/collector/status",
        )

    assert snapshot.status_code == 200
    assert status.status_code == 200
    assert (
        status.json()["financial_execution"]
        is False
    )


def test_opportunities_allows_authenticated_user(
    monkeypatch,
):
    monkeypatch.setattr(
        settings,
        "AUTH_REQUIRED_FOR_DASHBOARD",
        True,
    )

    monkeypatch.setattr(
        real_opportunity_radar,
        "real_opportunity_scan_service",
        RealOpportunityScanService(
            monitor=CountingMonitor(),
            clock=FakeClock(),
        ),
    )

    app = create_app()

    app.dependency_overrides[
        require_dashboard_user
    ] = lambda: None

    try:
        with TestClient(app) as client:
            response = client.get(
                "/real-markets/radar/opportunities",
            )
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
