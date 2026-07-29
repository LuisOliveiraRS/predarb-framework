from __future__ import annotations

import asyncio
import json
from datetime import (
    datetime,
    timedelta,
    timezone,
)

import pytest

from app.paper.certification_evidence_monitor import (
    PaperCertificationEvidenceMonitor,
)


NOW = datetime(
    2026,
    7,
    28,
    12,
    0,
    tzinfo=timezone.utc,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


def latest_entry(
    *,
    status="CERTIFIED",
    hours_old=1,
    scope="PAPER_ONLY",
):
    return {
        "status": status,
        "scope": scope,
        "certification_score": 100,
        "captured_at": (
            NOW
            - timedelta(
                hours=hours_old
            )
        ).isoformat(),
        **safe_flags(),
    }


class EvidenceStub:
    def __init__(
        self,
        *,
        total_entries=1,
        verification_status="VALID",
        verification_valid=True,
        latest=None,
    ):
        self.total_entries = total_entries
        self.verification_status = (
            verification_status
        )
        self.verification_valid = (
            verification_valid
        )
        self.latest_entry = (
            latest
            if latest is not None
            else (
                latest_entry()
                if total_entries
                else None
            )
        )

    def summary(self):
        return {
            "total_entries": self.total_entries,
            "chain_status": (
                self.verification_status
            ),
            "chain_valid": (
                self.verification_valid
            ),
            "chain_head": "a" * 64,
            **safe_flags(),
        }

    def verify(self):
        return {
            "status": self.verification_status,
            "valid": self.verification_valid,
            "total_entries": self.total_entries,
            "chain_head": "a" * 64,
            **safe_flags(),
        }

    def latest(self):
        return self.latest_entry


def monitor_for(
    stub,
    *,
    stale_hours=72,
):
    return PaperCertificationEvidenceMonitor(
        evidence_factory=lambda: stub,
        stale_hours=stale_hours,
        min_entries=1,
        now_provider=lambda: NOW,
    )


def test_monitor_returns_no_data():
    snapshot = monitor_for(
        EvidenceStub(
            total_entries=0,
            verification_status="EMPTY",
            verification_valid=True,
            latest=None,
        )
    ).snapshot()

    assert snapshot["status"] == "NO_DATA"
    assert snapshot["score"] == 0
    assert snapshot["alert_counts"][
        "info"
    ] == 1


def test_monitor_returns_healthy():
    snapshot = monitor_for(
        EvidenceStub()
    ).snapshot()

    assert snapshot["status"] == "HEALTHY"
    assert snapshot["score"] == 100
    assert snapshot["alerts"] == []
    assert snapshot[
        "live_authorization"
    ] is False


def test_monitor_warns_on_stale_evidence():
    snapshot = monitor_for(
        EvidenceStub(
            latest=latest_entry(
                hours_old=100
            )
        ),
        stale_hours=72,
    ).snapshot()

    assert snapshot["status"] == "WARNING"
    assert snapshot["score"] <= 79
    assert any(
        item["code"] == "EVIDENCE_STALE"
        for item in snapshot["alerts"]
    )


def test_monitor_is_critical_on_broken_chain():
    snapshot = monitor_for(
        EvidenceStub(
            verification_status="BROKEN",
            verification_valid=False,
        )
    ).snapshot()

    assert snapshot["status"] == "CRITICAL"
    assert snapshot["score"] < 50
    assert any(
        item["code"]
        == "EVIDENCE_CHAIN_BROKEN"
        for item in snapshot["alerts"]
    )


def test_monitor_is_critical_on_invalid_scope():
    snapshot = monitor_for(
        EvidenceStub(
            latest=latest_entry(
                scope="LIVE"
            )
        )
    ).snapshot()

    assert snapshot["status"] == "CRITICAL"
    assert any(
        item["code"]
        == "INVALID_EVIDENCE_SCOPE"
        for item in snapshot["alerts"]
    )


def test_monitor_rejects_unsafe_latest():
    unsafe = latest_entry()
    unsafe["live_authorization"] = True

    with pytest.raises(
        RuntimeError,
        match="latest",
    ):
        monitor_for(
            EvidenceStub(
                latest=unsafe
            )
        ).snapshot()


def test_dashboard_and_export_are_safe(
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_evidence_monitor
        as router_module,
    )

    expected = monitor_for(
        EvidenceStub()
    ).snapshot()

    monkeypatch.setattr(
        router_module,
        "_snapshot",
        lambda: expected,
    )

    dashboard = asyncio.run(
        router_module
        .evidence_monitor_dashboard()
    )

    body = dashboard.body.decode("utf-8")

    assert "Monitor de Evidências" in body
    assert "Nenhuma evidência é criada" in body
    assert (
        dashboard.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )

    response = asyncio.run(
        router_module
        .evidence_monitor_export_json()
    )

    payload = json.loads(
        response.body.decode("utf-8")
    )

    assert payload["status"] == "HEALTHY"
    assert payload["live_authorization"] is False


def test_application_registers_monitor_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_evidence_monitor import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(
            app.routes
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/certification/evidence/monitor/health",
        "/paper/certification/evidence/monitor/alerts",
        "/paper/certification/evidence/monitor/score",
        "/paper/certification/evidence/monitor/snapshot",
        "/paper/certification/evidence/monitor/dashboard",
        "/paper/certification/evidence/monitor/export.json",
    }

    assert not (
        required - paths
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert all(
        method_set == {"GET"}
        for method_set in methods.values()
    )
