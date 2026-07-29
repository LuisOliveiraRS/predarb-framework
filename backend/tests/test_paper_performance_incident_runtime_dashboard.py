from __future__ import annotations

import asyncio

from app.api.routers.paper_performance_incident_runtime_dashboard import (
    incident_runtime_dashboard,
    incident_runtime_dashboard_snapshot,
)


def safe_runtime_status():
    return {
        "status": "STOPPED",
        "enabled": True,
        "running": False,
        "interval_seconds": 60,
        "total_cycles": 2,
        "successful_cycles": 2,
        "failed_cycles": 0,
        "last_result": None,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "manual_start_required": True,
    }


def safe_incident_summary():
    return {
        "active_incidents": 1,
        "resolved_incidents": 2,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def safe_monitor_snapshot():
    return {
        "status": "HEALTHY",
        "score": 95,
        "alerts": [],
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def test_runtime_dashboard_is_safe_html():
    response = asyncio.run(
        incident_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Controle do Runtime" in body
    assert "Início manual obrigatório" in body
    assert "Execução financeira bloqueada" in body
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_runtime_dashboard_contains_confirmation_tokens():
    response = asyncio.run(
        incident_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    for token in (
        "START-PAPER-INCIDENT-RUNTIME",
        "STOP-PAPER-INCIDENT-RUNTIME",
        "CAPTURE-PAPER-INCIDENTS",
        "RESET-PAPER-INCIDENT-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_incidents_and_monitor(
    monkeypatch,
):
    runtime_calls = {
        "status": 0,
    }

    class RuntimeStub:
        def status(self):
            runtime_calls["status"] += 1
            return safe_runtime_status()

    class JournalStub:
        def summary(self):
            return safe_incident_summary()

    class MonitorStub:
        def snapshot(self):
            return safe_monitor_snapshot()

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "paper_incident_runtime",
        RuntimeStub(),
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "PaperIncidentJournal",
        JournalStub,
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "PaperPerformanceMonitor",
        MonitorStub,
    )

    payload = asyncio.run(
        incident_runtime_dashboard_snapshot()
    )

    assert runtime_calls["status"] == 1
    assert payload["runtime"]["running"] is False
    assert payload["incidents"][
        "active_incidents"
    ] == 1
    assert payload["monitor"]["status"] == "HEALTHY"
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False
    assert payload["manual_start_required"] is True


def test_snapshot_does_not_start_runtime_implicitly(
    monkeypatch,
):
    class RuntimeStub:
        started = False

        def status(self):
            return safe_runtime_status()

        async def start(self):
            self.started = True

    runtime = RuntimeStub()

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "paper_incident_runtime",
        runtime,
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "PaperIncidentJournal",
        lambda: type(
            "JournalStub",
            (),
            {
                "summary":
                    staticmethod(
                        safe_incident_summary
                    )
            },
        )(),
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_performance_incident_runtime_dashboard."
        "PaperPerformanceMonitor",
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

    asyncio.run(
        incident_runtime_dashboard_snapshot()
    )

    assert runtime.started is False


def test_application_registers_runtime_dashboard_routes():
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
        "/paper/performance/incidents/runtime/dashboard",
        "/paper/performance/incidents/runtime/snapshot",
    }

    assert not (
        required - paths
    )


def test_runtime_dashboard_routes_are_get_only():
    from app.api.routers.paper_performance_incident_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/performance/incidents/runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/performance/incidents/runtime/snapshot"
    ] == {"GET"}
