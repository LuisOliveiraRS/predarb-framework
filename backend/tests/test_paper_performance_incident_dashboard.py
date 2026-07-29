from __future__ import annotations

import asyncio
import csv
import io

from app.api.routers.paper_performance_incident_dashboard import (
    incident_dashboard,
    incident_dashboard_snapshot,
    incident_export_csv,
)
from app.paper.performance_incidents import (
    PaperIncidentJournal,
)


def alert():
    return {
        "code": "FAILED_CYCLE_RATE_HIGH",
        "severity": "warning",
        "title": "Taxa de falha elevada",
        "message": "Teste de dashboard",
        "current_value": 0.4,
        "threshold": 0.2,
    }


def safe_monitor_snapshot():
    return {
        "status": "WARNING",
        "score": 70,
        "alerts": [alert()],
        "alert_counts": {
            "critical": 0,
            "warning": 1,
            "info": 0,
        },
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def test_dashboard_html_preserves_financial_safety():
    response = asyncio.run(
        incident_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Incidentes Paper" in body
    assert "Execução financeira bloqueada" in body
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_snapshot_aggregates_journal_and_monitor(
    tmp_path,
    monkeypatch,
):
    journal_path = tmp_path / "incidents.json"

    monkeypatch.setenv(
        "PAPER_MONITOR_INCIDENTS_PATH",
        str(journal_path),
    )

    journal = PaperIncidentJournal(
        journal_path
    )

    journal.capture(
        safe_monitor_snapshot()
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_dashboard."
        "_monitor",
        lambda: type(
            "MonitorStub",
            (),
            {
                "snapshot":
                    staticmethod(
                        safe_monitor_snapshot
                    )
            },
        )(),
    )

    payload = asyncio.run(
        incident_dashboard_snapshot(
            active_limit=100,
            history_limit=250,
        )
    )

    assert payload["summary"][
        "active_incidents"
    ] == 1
    assert len(payload["active"]) == 1
    assert len(payload["history"]) == 1
    assert payload["monitor"]["status"] == "WARNING"
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False


def test_export_csv_contains_incident(
    tmp_path,
    monkeypatch,
):
    journal_path = tmp_path / "incidents.json"

    monkeypatch.setenv(
        "PAPER_MONITOR_INCIDENTS_PATH",
        str(journal_path),
    )

    PaperIncidentJournal(
        journal_path
    ).capture(
        safe_monitor_snapshot()
    )

    response = asyncio.run(
        incident_export_csv(
            limit=1000
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

    assert response.status_code == 200
    assert len(rows) == 1
    assert rows[0]["code"] == (
        "FAILED_CYCLE_RATE_HIGH"
    )
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_application_registers_incident_dashboard_routes():
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
        "/paper/performance/incidents/dashboard",
        "/paper/performance/incidents/snapshot",
        "/paper/performance/incidents/export.csv",
    }

    assert not (
        required - paths
    )


def test_incident_dashboard_routes_are_get_only():
    from app.api.routers.paper_performance_incident_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/performance/incidents/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/performance/incidents/snapshot"
    ] == {"GET"}

    assert methods[
        "/paper/performance/incidents/export.csv"
    ] == {"GET"}


def test_snapshot_does_not_capture_implicitly(
    tmp_path,
    monkeypatch,
):
    journal_path = tmp_path / "incidents.json"

    monkeypatch.setenv(
        "PAPER_MONITOR_INCIDENTS_PATH",
        str(journal_path),
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_dashboard."
        "_monitor",
        lambda: type(
            "MonitorStub",
            (),
            {
                "snapshot":
                    staticmethod(
                        safe_monitor_snapshot
                    )
            },
        )(),
    )

    payload = asyncio.run(
        incident_dashboard_snapshot(
            active_limit=100,
            history_limit=250,
        )
    )

    assert payload["summary"][
        "total_incidents"
    ] == 0
    assert not journal_path.exists()
