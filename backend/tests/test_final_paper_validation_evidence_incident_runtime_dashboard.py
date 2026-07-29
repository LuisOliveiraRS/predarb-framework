from __future__ import annotations

import asyncio

from app.api.routers import (
    paper_final_validation_evidence_incident_runtime_dashboard
    as router_module,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


class RuntimeStub:
    started = False

    def status(self):
        return {
            "status": "STOPPED",
            "running": False,
            "interval_seconds": 300,
            "total_cycles": 2,
            "successful_cycles": 2,
            "failed_cycles": 0,
            "created_incidents": 1,
            "resolved_incidents": 1,
            "last_result": None,
            "manual_start_required": True,
            **safe_flags(),
        }

    async def start(self):
        self.started = True


class MonitorStub:
    def evaluate(self):
        return {
            "status": "HEALTHY",
            "score": 100,
            "summary": {
                "integrity_status": "VALID",
            },
            "alerts": [],
            "read_only": True,
            **safe_flags(),
        }


class JournalStub:
    def summary(self):
        return {
            "active_incidents": 0,
            "resolved_incidents": 1,
            "active_critical": 0,
            "active_warning": 0,
            "total_snapshots": 2,
            "read_only": True,
            **safe_flags(),
        }


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .final_evidence_incident_runtime_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Runtime dos Incidentes Finais"
        in body
    )

    assert (
        "Início manual obrigatório"
        in body
    )

    assert (
        "START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME"
        in body
    )

    assert (
        "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME"
        in body
    )

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


def test_dashboard_contains_all_confirmation_tokens():
    response = asyncio.run(
        router_module
        .final_evidence_incident_runtime_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    for token in (
        "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS",
        "START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
        "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
        "RESET-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_monitor_and_journal(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "final_paper_evidence_incident_runtime",
        RuntimeStub(),
    )

    monkeypatch.setattr(
        router_module,
        "final_paper_validation_evidence_monitor",
        MonitorStub(),
    )

    monkeypatch.setattr(
        router_module,
        "FinalPaperEvidenceIncidentJournal",
        JournalStub,
    )

    payload = asyncio.run(
        router_module
        .final_evidence_incident_runtime_snapshot()
    )

    assert (
        payload["runtime"]["running"]
        is False
    )

    assert (
        payload["monitor"]["status"]
        == "HEALTHY"
    )

    assert (
        payload["journal"]["active_incidents"]
        == 0
    )

    assert (
        payload["manual_start_required"]
        is True
    )

    assert (
        payload["next_step_authorized"]
        is False
    )


def test_snapshot_does_not_start_runtime(
    monkeypatch,
):
    runtime = RuntimeStub()

    monkeypatch.setattr(
        router_module,
        "final_paper_evidence_incident_runtime",
        runtime,
    )

    monkeypatch.setattr(
        router_module,
        "final_paper_validation_evidence_monitor",
        MonitorStub(),
    )

    monkeypatch.setattr(
        router_module,
        "FinalPaperEvidenceIncidentJournal",
        JournalStub,
    )

    asyncio.run(
        router_module
        .final_evidence_incident_runtime_snapshot()
    )

    assert runtime.started is False


def test_application_registers_dashboard_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
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
        "/paper/final-validation/evidence/incident-runtime/dashboard",
        "/paper/final-validation/evidence/incident-runtime/snapshot",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_final_validation_evidence_incident_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/final-validation/evidence/incident-runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/final-validation/evidence/incident-runtime/snapshot"
    ] == {"GET"}
