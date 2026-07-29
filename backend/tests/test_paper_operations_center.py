from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.operations_center import (
    PaperOperationsCenter,
)


def performance_payload():
    return {
        "total_reports": 2,
        "total_cycles": 15,
        "total_trades": 18,
        "cumulative_equity_delta": 7.65,
        "endpoint_errors": 0,
        "safety_violations": 0,
        "execution_authorized": False,
        "live_execution": False,
    }


def monitor_payload(
    status="HEALTHY",
    score=95,
):
    return {
        "status": status,
        "score": score,
        "alerts": [],
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def incidents_payload(
    active_critical=0,
    active_warning=0,
):
    return {
        "active_incidents": (
            active_critical
            + active_warning
        ),
        "active_critical": active_critical,
        "active_warning": active_warning,
        "resolved_incidents": 2,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def runtime_payload(
    failed_cycles=0,
):
    return {
        "status": "STOPPED",
        "running": False,
        "interval_seconds": 60,
        "total_cycles": 4,
        "successful_cycles": 4,
        "failed_cycles": failed_cycles,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "manual_start_required": True,
    }


class Stub:
    def __init__(
        self,
        method_name,
        payload,
    ):
        setattr(
            self,
            method_name,
            lambda: payload,
        )


def center_with(
    *,
    performance=None,
    monitor=None,
    incidents=None,
    runtime=None,
):
    return PaperOperationsCenter(
        performance_factory=lambda: Stub(
            "summary",
            performance or performance_payload(),
        ),
        monitor_factory=lambda: Stub(
            "snapshot",
            monitor or monitor_payload(),
        ),
        journal_factory=lambda: Stub(
            "summary",
            incidents or incidents_payload(),
        ),
        runtime=Stub(
            "status",
            runtime or runtime_payload(),
        ),
    )


def test_operations_center_returns_healthy_snapshot():
    payload = center_with().snapshot()

    assert payload["status"] == "HEALTHY"
    assert payload["diagnostics"]["reports"] == 2
    assert payload["diagnostics"]["trades"] == 18
    assert payload["manual_start_required"] is True
    assert payload["read_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False


def test_operations_center_propagates_critical_state():
    payload = center_with(
        monitor=monitor_payload(
            status="CRITICAL",
            score=50,
        )
    ).snapshot()

    assert payload["status"] == "CRITICAL"


def test_operations_center_warns_on_runtime_failure():
    payload = center_with(
        runtime=runtime_payload(
            failed_cycles=1
        )
    ).snapshot()

    assert payload["status"] == "WARNING"
    assert payload["diagnostics"][
        "runtime_failures"
    ] == 1


def test_operations_center_rejects_unsafe_component():
    unsafe = performance_payload()
    unsafe["live_execution"] = True

    with pytest.raises(
        RuntimeError,
        match="performance",
    ):
        center_with(
            performance=unsafe
        ).snapshot()


def test_operations_dashboard_is_safe_html():
    from app.api.routers.paper_operations_center import (
        paper_operations_dashboard,
    )

    response = asyncio.run(
        paper_operations_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Centro de Operações Paper" in body
    assert "Execução financeira bloqueada" in body
    assert "Centro somente leitura" in body
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_operations_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_operations_center as router_module,
    )

    expected = center_with().snapshot()

    monkeypatch.setattr(
        router_module,
        "_snapshot",
        lambda: expected,
    )

    response = asyncio.run(
        router_module.paper_operations_export_json()
    )

    payload = json.loads(
        response.body.decode("utf-8")
    )

    assert payload["status"] == "HEALTHY"
    assert payload["financial_execution"] is False
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_application_registers_operations_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.core.application import create_app
    from app.api.routers.paper_operations_center import (
        router,
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
        "/paper/operations/health",
        "/paper/operations/snapshot",
        "/paper/operations/dashboard",
        "/paper/operations/export.json",
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
        value == {"GET"}
        for value in methods.values()
    )
