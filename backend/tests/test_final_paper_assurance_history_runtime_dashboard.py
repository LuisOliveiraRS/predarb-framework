from __future__ import annotations

import asyncio

from app.api.routers import (
    paper_final_assurance_history_runtime_dashboard
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
            "assured_cycles": 2,
            "warning_cycles": 0,
            "blocked_cycles": 0,
            "no_data_cycles": 0,
            "last_result": None,
            "manual_start_required": True,
            **safe_flags(),
        }

    async def start(self):
        self.started = True


class AssuranceStub:
    def evaluate(self):
        return {
            "status": "ASSURED",
            "assured": True,
            "scope": "PAPER_ASSURANCE_ONLY",
            "assurance_score": 100,
            "summary": {
                "integrity_status": "VALID",
            },
            "checks": [],
            "failures": [],
            "read_only": True,
            **safe_flags(),
        }


class HistoryStub:
    def summary(self):
        return {
            "total_entries": 3,
            "latest_status": "ASSURED",
            "latest_score": 100,
            "longest_assured_streak": 3,
            "transitions": 0,
            "read_only": True,
            **safe_flags(),
        }


def test_dashboard_is_safe_html():
    response = asyncio.run(
        router_module
        .final_assurance_history_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    assert (
        "Runtime do Histórico da Garantia Final"
        in body
    )
    assert (
        "Início manual obrigatório"
        in body
    )
    assert (
        "START-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME"
        in body
    )
    assert (
        "STOP-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME"
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
        .final_assurance_history_runtime_dashboard()
    )

    body = response.body.decode("utf-8")

    for token in (
        "CAPTURE-FINAL-PAPER-ASSURANCE",
        "START-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME",
        "STOP-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME",
        "RESET-FINAL-PAPER-ASSURANCE-HISTORY-RUNTIME",
    ):
        assert token in body


def test_snapshot_aggregates_runtime_assurance_and_history(
    monkeypatch,
):
    monkeypatch.setattr(
        router_module,
        "final_paper_assurance_history_runtime",
        RuntimeStub(),
    )
    monkeypatch.setattr(
        router_module,
        "final_paper_operational_assurance",
        AssuranceStub(),
    )
    monkeypatch.setattr(
        router_module,
        "FinalPaperOperationalAssuranceHistory",
        HistoryStub,
    )

    payload = asyncio.run(
        router_module
        .final_assurance_history_runtime_snapshot()
    )

    assert payload["runtime"]["running"] is False
    assert payload["assurance"]["status"] == "ASSURED"
    assert payload["history"]["total_entries"] == 3
    assert payload["manual_start_required"] is True
    assert payload["next_step_authorized"] is False


def test_snapshot_does_not_start_runtime(
    monkeypatch,
):
    runtime = RuntimeStub()

    monkeypatch.setattr(
        router_module,
        "final_paper_assurance_history_runtime",
        runtime,
    )
    monkeypatch.setattr(
        router_module,
        "final_paper_operational_assurance",
        AssuranceStub(),
    )
    monkeypatch.setattr(
        router_module,
        "FinalPaperOperationalAssuranceHistory",
        HistoryStub,
    )

    asyncio.run(
        router_module
        .final_assurance_history_runtime_snapshot()
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
        "/paper/final-assurance/history-runtime/dashboard",
        "/paper/final-assurance/history-runtime/snapshot",
    }

    assert not (required - paths)


def test_dashboard_routes_are_get_only():
    from app.api.routers.paper_final_assurance_history_runtime_dashboard import (
        router,
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/final-assurance/history-runtime/dashboard"
    ] == {"GET"}

    assert methods[
        "/paper/final-assurance/history-runtime/snapshot"
    ] == {"GET"}
