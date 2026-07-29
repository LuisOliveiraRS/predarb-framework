from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.certification_assurance_center import (
    PaperCertificationAssuranceCenter,
)


def safe_flags(
    *,
    read_only=True,
):
    payload = {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }

    if read_only:
        payload["read_only"] = True

    return payload


def certification_payload(
    status="CERTIFIED",
    score=100,
):
    return {
        "status": status,
        "certification_score": score,
        **safe_flags(),
    }


def evidence_summary_payload():
    return {
        "total_entries": 5,
        **safe_flags(),
    }


def verification_payload(
    status="VALID",
    valid=True,
):
    return {
        "status": status,
        "valid": valid,
        **safe_flags(),
    }


def monitor_payload(
    status="HEALTHY",
    score=100,
):
    return {
        "status": status,
        "score": score,
        **safe_flags(),
    }


def incidents_payload(
    *,
    active=0,
    critical=0,
    warning=0,
):
    return {
        "active_incidents": active,
        "active_critical": critical,
        "active_warning": warning,
        **safe_flags(),
    }


def runtime_payload(
    *,
    failures=0,
):
    return {
        "status": "STOPPED",
        "total_cycles": 3,
        "failed_cycles": failures,
        **safe_flags(
            read_only=False
        ),
    }


class CertificationStub:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def evaluate(self):
        return self.payload


class EvidenceStub:
    def __init__(
        self,
        summary,
        verification,
    ):
        self.summary_payload = summary
        self.verification_payload = (
            verification
        )

    def summary(self):
        return self.summary_payload

    def verify(self):
        return self.verification_payload


class MonitorStub:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def snapshot(self):
        return self.payload


class IncidentsStub:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def summary(self):
        return self.payload


class RuntimeStub:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def status(self):
        return self.payload


def patch_components(
    monkeypatch,
    *,
    certification=None,
    evidence_summary=None,
    verification=None,
    monitor=None,
    incidents=None,
    runtime=None,
):
    import app.paper.certification_assurance_center as module

    monkeypatch.setattr(
        module,
        "paper_stability_certification",
        CertificationStub(
            certification
            or certification_payload()
        ),
    )

    monkeypatch.setattr(
        module,
        "PaperCertificationEvidence",
        lambda: EvidenceStub(
            evidence_summary
            or evidence_summary_payload(),
            verification
            or verification_payload(),
        ),
    )

    monkeypatch.setattr(
        module,
        "paper_certification_evidence_monitor",
        MonitorStub(
            monitor
            or monitor_payload()
        ),
    )

    monkeypatch.setattr(
        module,
        "PaperCertificationEvidenceIncidentJournal",
        lambda: IncidentsStub(
            incidents
            or incidents_payload()
        ),
    )

    monkeypatch.setattr(
        module,
        "paper_evidence_incident_runtime",
        RuntimeStub(
            runtime
            or runtime_payload()
        ),
    )


def test_assurance_returns_assured(
    monkeypatch,
):
    patch_components(
        monkeypatch
    )

    snapshot = (
        PaperCertificationAssuranceCenter()
        .snapshot()
    )

    assert snapshot["status"] == "ASSURED"
    assert snapshot["assured"] is True
    assert snapshot["scope"] == "PAPER_ONLY"
    assert snapshot["live_authorization"] is False


def test_assurance_is_critical_on_broken_chain(
    monkeypatch,
):
    patch_components(
        monkeypatch,
        verification=(
            verification_payload(
                status="BROKEN",
                valid=False,
            )
        ),
    )

    snapshot = (
        PaperCertificationAssuranceCenter()
        .snapshot()
    )

    assert snapshot["status"] == "CRITICAL"
    assert snapshot["assurance_score"] < 50


def test_assurance_is_blocked_by_certification(
    monkeypatch,
):
    patch_components(
        monkeypatch,
        certification=(
            certification_payload(
                status="BLOCKED",
                score=70,
            )
        ),
    )

    snapshot = (
        PaperCertificationAssuranceCenter()
        .snapshot()
    )

    assert snapshot["status"] == "BLOCKED"
    assert snapshot["assured"] is False


def test_assurance_rejects_unsafe_component(
    monkeypatch,
):
    unsafe = monitor_payload()
    unsafe["live_execution"] = True

    patch_components(
        monkeypatch,
        monitor=unsafe,
    )

    with pytest.raises(
        RuntimeError,
        match="monitor",
    ):
        (
            PaperCertificationAssuranceCenter()
            .snapshot()
        )


def test_dashboard_is_safe_html():
    from app.api.routers.paper_certification_assurance import (
        certification_assurance_dashboard,
    )

    response = asyncio.run(
        certification_assurance_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Centro de Garantia Paper"
        in body
    )
    assert (
        "Não autoriza execução live"
        in body
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_assurance
        as router_module,
    )

    expected = {
        "status": "ASSURED",
        "assured": True,
        "scope": "PAPER_ONLY",
        "assurance_score": 100,
        "summary": {},
        **safe_flags(),
    }

    monkeypatch.setattr(
        router_module,
        "_snapshot",
        lambda: expected,
    )

    response = asyncio.run(
        router_module
        .certification_assurance_export_json()
    )

    payload = json.loads(
        response.body.decode(
            "utf-8"
        )
    )

    assert payload["status"] == "ASSURED"
    assert payload["live_authorization"] is False
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_application_registers_assurance_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_assurance import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/certification/assurance/health",
        "/paper/certification/assurance/snapshot",
        "/paper/certification/assurance/dashboard",
        "/paper/certification/assurance/export.json",
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
