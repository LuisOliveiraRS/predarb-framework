from __future__ import annotations

import asyncio

from app.api.routers.paper_readiness_runtime_dashboard import (
    readiness_runtime_dashboard,
    readiness_runtime_dashboard_snapshot,
)


def safe_runtime():
    return {
        "status": "STOPPED",
        "enabled": True,
        "running": False,
        "interval_seconds": 300,
        "total_cycles": 3,
        "successful_cycles": 3,
        "failed_cycles": 0,
        "ready_cycles": 1,
        "not_ready_cycles": 0,
        "insufficient_data_cycles": 2,
        "last_result": None,
        "manual_start_required": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def safe_gate():
    return {
        "status": "INSUFFICIENT_DATA",
        "ready": False,
        "readiness_score": 72.73,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def safe_history():
    return {
        "total_entries": 3,
        "latest_status": "INSUFFICIENT_DATA",
        "latest_score": 72.73,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def test_dashboard_is_safe_html():
    response = asyncio.run(
        readiness_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Runtime de Readiness" in body
    assert "Início manual obrigatório" in body
    assert "Execução financeira bloqueada" in body
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_dashboard_contains_confirmation_tokens():
    response = asyncio.run(
        readiness_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    for token in (
        "CAPTURE-PAPER-READINESS",
        "START-PAPER-READINESS-RUNTIME",
        "STOP-PAPER-READINESS-RUNTIME",
        "RESET-PAPER-READINESS-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_gate_and_history(
    monkeypatch,
):
    class RuntimeStub:
        def status(self):
            return safe_runtime()

    class GateStub:
        def evaluate(self):
            return safe_gate()

    class HistoryStub:
        def summary(self):
            return safe_history()

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "paper_readiness_runtime",
        RuntimeStub(),
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "PaperReadinessGate",
        GateStub,
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "PaperReadinessHistory",
        HistoryStub,
    )

    payload = asyncio.run(
        readiness_runtime_dashboard_snapshot()
    )

    assert payload["runtime"]["running"] is False
    assert payload["gate"]["status"] == (
        "INSUFFICIENT_DATA"
    )
    assert payload["history"][
        "total_entries"
    ] == 3
    assert payload["manual_start_required"] is True
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False


def test_snapshot_does_not_start_runtime(
    monkeypatch,
):
    class RuntimeStub:
        started = False

        def status(self):
            return safe_runtime()

        async def start(self):
            self.started = True

    runtime = RuntimeStub()

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "paper_readiness_runtime",
        runtime,
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "PaperReadinessGate",
        lambda: type(
            "GateStub",
            (),
            {
                "evaluate":
                    staticmethod(
                        safe_gate
                    )
            },
        )(),
    )

    monkeypatch.setattr(
        "app.api.routers."
        "paper_readiness_runtime_dashboard."
        "PaperReadinessHistory",
        lambda: type(
            "HistoryStub",
            (),
            {
                "summary":
                    staticmethod(
                        safe_history
                    )
            },
        )(),
    )

    asyncio.run(
        readiness_runtime_dashboard_snapshot()
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
        for context in iter_route_contexts(
            app.routes
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/readiness/runtime/dashboard",
        "/paper/readiness/runtime/snapshot",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_readiness_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/readiness/runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/readiness/runtime/snapshot"
    ] == {"GET"}
