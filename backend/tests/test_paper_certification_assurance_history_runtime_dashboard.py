from __future__ import annotations

import asyncio

from app.api.routers import (
    paper_certification_assurance_history_runtime_dashboard
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


def assurance_payload():
    return {
        "status": "ASSURED",
        "assured": True,
        "scope": "PAPER_ONLY",
        "assurance_score": 100,
        "read_only": True,
        **safe_flags(),
    }


def history_payload():
    return {
        "total_entries": 4,
        "latest_status": "ASSURED",
        "longest_assured_streak": 3,
        "read_only": True,
        **safe_flags(),
    }


class RuntimeStub:
    started = False

    def status(self):
        return runtime_payload()

    async def start(self):
        self.started = True


class AssuranceStub:
    def snapshot(self):
        return assurance_payload()


class HistoryStub:
    def summary(self):
        return history_payload()


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .assurance_history_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert (
        "Runtime do Histórico da Garantia"
        in body
    )
    assert "Início manual obrigatório" in body
    assert (
        "Somente snapshots são persistidos"
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
        .assurance_history_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    for token in (
        "CAPTURE-PAPER-CERTIFICATION-ASSURANCE",
        "START-PAPER-ASSURANCE-HISTORY-RUNTIME",
        "STOP-PAPER-ASSURANCE-HISTORY-RUNTIME",
        "RESET-PAPER-ASSURANCE-HISTORY-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_assurance_and_history(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "paper_assurance_history_runtime",
        RuntimeStub(),
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_assurance_center",
        AssuranceStub(),
    )

    monkeypatch.setattr(
        router_module,
        "PaperCertificationAssuranceHistory",
        HistoryStub,
    )

    payload = asyncio.run(
        router_module
        .assurance_history_runtime_dashboard_snapshot()
    )

    assert payload["runtime"]["running"] is False
    assert payload["assurance"]["status"] == "ASSURED"
    assert payload["history"]["total_entries"] == 4
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
        "paper_assurance_history_runtime",
        runtime,
    )

    monkeypatch.setattr(
        router_module,
        "paper_certification_assurance_center",
        AssuranceStub(),
    )

    monkeypatch.setattr(
        router_module,
        "PaperCertificationAssuranceHistory",
        HistoryStub,
    )

    asyncio.run(
        router_module
        .assurance_history_runtime_dashboard_snapshot()
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
        "/paper/certification/assurance/history-runtime/dashboard",
        "/paper/certification/assurance/history-runtime/snapshot",
    }

    assert not (
        required - paths
    )


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_certification_assurance_history_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/certification/assurance/history-runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/certification/assurance/history-runtime/snapshot"
    ] == {"GET"}
