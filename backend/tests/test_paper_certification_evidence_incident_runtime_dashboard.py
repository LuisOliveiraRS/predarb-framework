from __future__ import annotations

import asyncio

from app.api.routers import (
    paper_certification_evidence_incident_runtime_dashboard
    as router_module,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def runtime_payload():
    return {
        "status": "STOPPED",
        "enabled": True,
        "running": False,
        "interval_seconds": 300,
        "total_cycles": 2,
        "successful_cycles": 2,
        "failed_cycles": 0,
        "last_result": None,
        "manual_start_required": True,
        **safe_flags(),
    }


def monitor_payload():
    return {
        "status": "HEALTHY",
        "score": 100,
        "alerts": [],
        "diagnostics": {
            "chain_status": "VALID",
        },
        "read_only": True,
        **safe_flags(),
    }


def journal_payload():
    return {
        "active_incidents": 0,
        "resolved_incidents": 1,
        "snapshots": 2,
        "read_only": True,
        **safe_flags(),
    }


class RuntimeStub:
    started = False

    def status(self):
        return runtime_payload()

    async def start(self):
        self.started = True


class MonitorStub:
    def snapshot(self):
        return monitor_payload()


class JournalStub:
    def summary(self):
        return journal_payload()


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .evidence_incident_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert (
        "Runtime dos Incidentes das Evidências"
        in body
    )
    assert "Início manual obrigatório" in body
    assert "Nenhuma evidência é criada" in body
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_dashboard_contains_confirmation_tokens():
    response = asyncio.run(
        router_module
        .evidence_incident_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    for token in (
        "CAPTURE-PAPER-EVIDENCE-INCIDENTS",
        "START-PAPER-EVIDENCE-INCIDENT-RUNTIME",
        "STOP-PAPER-EVIDENCE-INCIDENT-RUNTIME",
        "RESET-PAPER-EVIDENCE-INCIDENT-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_monitor_and_journal(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "paper_evidence_incident_runtime",
        RuntimeStub(),
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_evidence_monitor",
        MonitorStub(),
    )

    monkeypatch.setattr(
        router_module,
        "PaperCertificationEvidenceIncidentJournal",
        JournalStub,
    )

    payload = asyncio.run(
        router_module
        .evidence_incident_runtime_dashboard_snapshot()
    )

    assert payload["runtime"]["running"] is False
    assert payload["monitor"]["status"] == "HEALTHY"
    assert payload["journal"]["snapshots"] == 2
    assert payload["manual_start_required"] is True
    assert payload["execution_authorized"] is False
    assert payload["live_authorization"] is False
    assert payload["financial_execution"] is False


def test_snapshot_does_not_start_runtime(
    monkeypatch,
):
    runtime = RuntimeStub()

    monkeypatch.setattr(
        router_module,
        "paper_evidence_incident_runtime",
        runtime,
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_evidence_monitor",
        MonitorStub(),
    )

    monkeypatch.setattr(
        router_module,
        "PaperCertificationEvidenceIncidentJournal",
        JournalStub,
    )

    asyncio.run(
        router_module
        .evidence_incident_runtime_dashboard_snapshot()
    )

    assert runtime.started is False


def test_application_registers_dashboard_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
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
        "/paper/certification/evidence/incident-runtime/dashboard",
        "/paper/certification/evidence/incident-runtime/snapshot",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_certification_evidence_incident_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/certification/evidence/incident-runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/certification/evidence/incident-runtime/snapshot"
    ] == {"GET"}
