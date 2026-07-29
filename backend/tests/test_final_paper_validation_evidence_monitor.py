from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

from app.paper.final_paper_validation_evidence_monitor import (
    EvidenceMonitorThresholds,
    FinalPaperValidationEvidenceMonitor,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


class EvidenceStub:
    def __init__(
        self,
        *,
        total_entries=1,
        integrity_status="VALID",
        valid=True,
        latest_status="PAPER_VALIDATED",
        captured_at=None,
        unsafe=False,
    ):
        self.total_entries = total_entries
        self.integrity_status = integrity_status
        self.valid = valid
        self.latest_status = latest_status
        self.captured_at = (
            captured_at
            or "2026-07-28T12:00:00+00:00"
        )
        self.unsafe = unsafe

    def summary(self):
        payload = {
            "total_entries": self.total_entries,
            "chain_head": (
                "abc123"
                if self.total_entries
                else None
            ),
            **safe_flags(),
        }

        if self.unsafe:
            payload["live_execution"] = True

        return payload

    def verify(self):
        return {
            "integrity_status": self.integrity_status,
            "valid": self.valid,
            "reason": (
                None
                if self.valid
                else "tampering"
            ),
            **safe_flags(),
        }

    def latest(self):
        if not self.total_entries:
            return None

        return {
            "status": self.latest_status,
            "scope": "PAPER_VALIDATION_ONLY",
            "captured_at": self.captured_at,
            **safe_flags(),
        }


def monitor_for(
    evidence,
    *,
    now=None,
):
    return FinalPaperValidationEvidenceMonitor(
        evidence=evidence,
        thresholds=EvidenceMonitorThresholds(
            stale_hours=72,
            min_entries=1,
        ),
        now_provider=(
            lambda: (
                now
                or datetime(
                    2026,
                    7,
                    28,
                    13,
                    0,
                    tzinfo=timezone.utc,
                )
            )
        ),
    )


def test_monitor_returns_no_data():
    snapshot = monitor_for(
        EvidenceStub(
            total_entries=0
        )
    ).evaluate()

    assert snapshot["status"] == "NO_DATA"
    assert snapshot["score"] == 0
    assert snapshot["summary"]["total_entries"] == 0


def test_monitor_returns_healthy():
    snapshot = monitor_for(
        EvidenceStub()
    ).evaluate()

    assert snapshot["status"] == "HEALTHY"
    assert snapshot["score"] == 100
    assert snapshot["alerts"] == []


def test_monitor_detects_broken_chain():
    snapshot = monitor_for(
        EvidenceStub(
            integrity_status="BROKEN",
            valid=False,
        )
    ).evaluate()

    assert snapshot["status"] == "CRITICAL"
    assert snapshot["score"] <= 49
    assert any(
        item["code"] == "CHAIN_BROKEN"
        for item in snapshot["alerts"]
    )


def test_monitor_detects_blocked_validation():
    snapshot = monitor_for(
        EvidenceStub(
            latest_status="PAPER_BLOCKED"
        )
    ).evaluate()

    assert snapshot["status"] == "CRITICAL"
    assert any(
        item["code"] == "LATEST_VALIDATION_BLOCKED"
        for item in snapshot["alerts"]
    )


def test_monitor_detects_stale_evidence():
    now = datetime(
        2026,
        7,
        28,
        13,
        0,
        tzinfo=timezone.utc,
    )

    stale = (
        now
        - timedelta(hours=100)
    ).isoformat()

    snapshot = monitor_for(
        EvidenceStub(
            captured_at=stale
        ),
        now=now,
    ).evaluate()

    assert snapshot["status"] == "WARNING"
    assert snapshot["score"] <= 79
    assert any(
        item["code"] == "STALE_EVIDENCE"
        for item in snapshot["alerts"]
    )


def test_monitor_rejects_unsafe_payload():
    with pytest.raises(
        RuntimeError,
        match="evidence_summary",
    ):
        monitor_for(
            EvidenceStub(
                unsafe=True
            )
        ).evaluate()


def test_dashboard_is_safe_html():
    from app.api.routers.paper_final_validation_evidence_monitor import (
        final_evidence_monitor_dashboard,
    )

    response = asyncio.run(
        final_evidence_monitor_dashboard()
    )

    body = response.body.decode("utf-8")

    assert (
        "Monitor das Evidências Finais"
        in body
    )
    assert "Somente leitura" in body
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )
    assert (
        response.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )


def test_application_registers_monitor_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_validation_evidence_monitor import (
        router,
    )
    from app.core.application import create_app

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
        "/paper/final-validation/evidence/monitor/health",
        "/paper/final-validation/evidence/monitor/alerts",
        "/paper/final-validation/evidence/monitor/score",
        "/paper/final-validation/evidence/monitor/snapshot",
        "/paper/final-validation/evidence/monitor/dashboard",
        "/paper/final-validation/evidence/monitor/export.json",
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
