from __future__ import annotations

import asyncio
import csv
import io

from app.api.routers import (
    paper_certification_evidence_incident_dashboard
    as router_module,
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


def summary_payload():
    return {
        "active_incidents": 1,
        "active_critical": 0,
        "active_warning": 1,
        "active_info": 0,
        "resolved_incidents": 2,
        "snapshots": 4,
        **safe_flags(),
    }


def incident_payload():
    return {
        "id": "evidence-incident-123",
        "status": "ACTIVE",
        "severity": "warning",
        "code": "EVIDENCE_STALE",
        "title": "Evidência desatualizada",
        "message": "A evidência está antiga.",
        "current_value": 100,
        "threshold": 72,
        "first_seen_at":
            "2026-07-28T10:00:00+00:00",
        "last_seen_at":
            "2026-07-28T12:00:00+00:00",
        "resolved_at": None,
        "reactivated_at": None,
        "occurrences": 2,
        "reactivations": 0,
        "acknowledged": False,
        "acknowledged_at": None,
        "acknowledged_by": None,
        "acknowledgement_note": None,
        **safe_flags(),
    }


def monitor_payload():
    return {
        "status": "WARNING",
        "score": 79,
        "diagnostics": {
            "chain_status": "VALID",
        },
        **safe_flags(),
    }


class JournalStub:
    def summary(self):
        return summary_payload()

    def list_incidents(
        self,
        *,
        status=None,
        limit=250,
    ):
        item = incident_payload()

        if status == "ACTIVE":
            return [item]

        return [item]

    def list_snapshots(
        self,
        *,
        limit=250,
    ):
        return [
            {
                "status": "WARNING",
                **safe_flags(),
            }
        ]


class MonitorStub:
    def snapshot(self):
        return monitor_payload()


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .evidence_incident_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert (
        "Incidentes das Evidências"
        in body
    )
    assert (
        "Reconhecimento não resolve alerta"
        in body
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_dashboard_contains_confirmation_tokens():
    response = asyncio.run(
        router_module
        .evidence_incident_dashboard()
    )

    body = response.body.decode("utf-8")

    assert (
        "CAPTURE-PAPER-EVIDENCE-INCIDENTS"
        in body
    )
    assert (
        "ACK-PAPER-EVIDENCE-INCIDENT"
        in body
    )


def test_snapshot_aggregates_data(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "_journal",
        lambda: JournalStub(),
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_evidence_monitor",
        MonitorStub(),
    )

    payload = asyncio.run(
        router_module
        .evidence_incident_dashboard_snapshot(
            limit=250
        )
    )

    assert payload["summary"][
        "active_incidents"
    ] == 1

    assert payload["monitor"][
        "status"
    ] == "WARNING"

    assert len(payload["active"]) == 1
    assert len(payload["history"]) == 1
    assert payload[
        "execution_authorized"
    ] is False
    assert payload[
        "live_authorization"
    ] is False


def test_snapshot_has_no_capture_side_effect(
    monkeypatch,
):
    class JournalNoCaptureStub(
        JournalStub
    ):
        captured = False

        def capture(self, snapshot):
            self.captured = True

    journal = (
        JournalNoCaptureStub()
    )

    monkeypatch.setattr(
        router_module,
        "_journal",
        lambda: journal,
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_evidence_monitor",
        MonitorStub(),
    )

    asyncio.run(
        router_module
        .evidence_incident_dashboard_snapshot(
            limit=250
        )
    )

    assert journal.captured is False


def test_export_csv_is_safe(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "_journal",
        lambda: JournalStub(),
    )

    response = asyncio.run(
        router_module
        .evidence_incident_dashboard_export_csv(
            limit=5000
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
    assert rows[0]["code"] == (
        "EVIDENCE_STALE"
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
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
        "/paper/certification/evidence/incidents/ui/dashboard",
        "/paper/certification/evidence/incidents/ui/snapshot",
        "/paper/certification/evidence/incidents/ui/export.csv",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_certification_evidence_incident_dashboard import (
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
