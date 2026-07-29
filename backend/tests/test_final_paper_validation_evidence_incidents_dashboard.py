from __future__ import annotations

import asyncio
import csv
import io

from app.api.routers import (
    paper_final_validation_evidence_incidents_dashboard
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
        "read_only": True,
    }


class JournalStub:
    def summary(self):
        return {
            "active_incidents": 1,
            "resolved_incidents": 2,
            "active_critical": 1,
            "active_warning": 0,
            "unacknowledged_active": 1,
            "total_snapshots": 3,
            **safe_flags(),
        }

    def list_incidents(
        self,
        *,
        status=None,
        limit=500,
    ):
        items = [
            {
                "id": "fpe-1",
                "status": "ACTIVE",
                "severity": "critical",
                "code": "CHAIN_BROKEN",
                "title": "Cadeia corrompida",
                "message": "Mensagem",
                "first_seen_at": "2026-07-28T12:00:00+00:00",
                "last_seen_at": "2026-07-28T13:00:00+00:00",
                "resolved_at": None,
                "occurrences": 2,
                "reactivations": 0,
                "acknowledged_at": None,
                "acknowledged_by": None,
                "current_value": "BROKEN",
                "expected_value": "VALID",
                **safe_flags(),
            }
        ]

        if status == "RESOLVED":
            return []

        return items[:limit]


class MonitorStub:
    def evaluate(self):
        return {
            "status": "CRITICAL",
            "score": 49,
            "summary": {
                "integrity_status": "BROKEN",
            },
            "alerts": [],
            **safe_flags(),
        }


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .final_evidence_incident_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Incidentes das Evidências Finais"
        in body
    )

    assert (
        "Captura manual confirmada"
        in body
    )

    assert (
        "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS"
        in body
    )

    assert (
        "ACK-FINAL-PAPER-EVIDENCE-INCIDENT"
        in body
    )

    assert (
        response.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )


def test_snapshot_aggregates_monitor_and_journal(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "_journal",
        JournalStub,
    )

    monkeypatch.setattr(
        router_module,
        "final_paper_validation_evidence_monitor",
        MonitorStub(),
    )

    payload = asyncio.run(
        router_module
        .final_evidence_incident_dashboard_snapshot()
    )

    assert (
        payload["summary"]["active_incidents"]
        == 1
    )

    assert (
        payload["monitor"]["status"]
        == "CRITICAL"
    )

    assert (
        len(payload["active"])
        == 1
    )

    assert (
        payload["next_step_authorized"]
        is False
    )


def test_snapshot_has_no_capture_side_effect(
    monkeypatch,
):
    class NoCaptureJournal(
        JournalStub
    ):
        def capture(self):
            raise AssertionError(
                "capture não deveria ser chamado"
            )

    monkeypatch.setattr(
        router_module,
        "_journal",
        NoCaptureJournal,
    )

    monkeypatch.setattr(
        router_module,
        "final_paper_validation_evidence_monitor",
        MonitorStub(),
    )

    asyncio.run(
        router_module
        .final_evidence_incident_dashboard_snapshot()
    )


def test_export_csv_is_safe(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "_journal",
        JournalStub,
    )

    response = asyncio.run(
        router_module
        .final_evidence_incident_dashboard_export_csv(
            limit=100
        )
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                response.body.decode(
                    "utf-8-sig"
                )
            )
        )
    )

    assert len(rows) == 1

    assert (
        rows[0]["code"]
        == "CHAIN_BROKEN"
    )

    assert (
        response.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )


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
        "/paper/final-validation/evidence/incidents/ui/dashboard",
        "/paper/final-validation/evidence/incidents/ui/snapshot",
        "/paper/final-validation/evidence/incidents/ui/export.csv",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_final_validation_evidence_incidents_dashboard import (
        router,
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
