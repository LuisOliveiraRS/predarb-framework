from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.readiness import (
    PaperReadinessGate,
    ReadinessThresholds,
)


def operations_payload(
    *,
    reports=3,
    cycles=40,
    trades=20,
    endpoint_errors=0,
    safety_violations=0,
    monitor_status="HEALTHY",
    monitor_score=92,
    active_critical=0,
    active_warning=0,
    runtime_failures=0,
):
    return {
        "status": "HEALTHY",
        "performance": {
            "total_reports": reports,
            "total_cycles": cycles,
            "total_trades": trades,
            "endpoint_errors": endpoint_errors,
            "safety_violations": safety_violations,
            "execution_authorized": False,
            "live_execution": False,
        },
        "monitor": {
            "status": monitor_status,
            "score": monitor_score,
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        },
        "incidents": {
            "active_incidents": (
                active_critical
                + active_warning
            ),
            "active_critical": active_critical,
            "active_warning": active_warning,
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        },
        "runtime": {
            "failed_cycles": runtime_failures,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        },
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


class OperationsStub:
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def snapshot(self):
        return self.payload


def gate_for(payload):
    return PaperReadinessGate(
        operations_center=OperationsStub(
            payload
        ),
        thresholds=ReadinessThresholds(
            min_reports=2,
            min_cycles=20,
            min_trades=10,
            min_monitor_score=75,
            max_active_warning_incidents=5,
            max_runtime_failures=0,
        ),
    )


def test_readiness_gate_returns_ready():
    report = gate_for(
        operations_payload()
    ).evaluate()

    assert report["status"] == "READY"
    assert report["ready"] is True
    assert report["summary"]["blockers"] == 0
    assert report["summary"][
        "insufficient_data"
    ] == 0
    assert report["financial_execution"] is False


def test_readiness_gate_reports_insufficient_data():
    report = gate_for(
        operations_payload(
            reports=1,
            cycles=5,
            trades=2,
        )
    ).evaluate()

    assert report["status"] == (
        "INSUFFICIENT_DATA"
    )
    assert report["ready"] is False
    assert report["summary"][
        "insufficient_data"
    ] == 3


def test_readiness_gate_blocks_critical_monitor():
    report = gate_for(
        operations_payload(
            monitor_status="CRITICAL",
            monitor_score=50,
        )
    ).evaluate()

    assert report["status"] == "NOT_READY"
    assert report["summary"]["blockers"] >= 1
    assert any(
        item["code"]
        == "MONITOR_STATUS_ACCEPTABLE"
        for item in report["blockers"]
    )


def test_readiness_gate_blocks_safety_violation():
    report = gate_for(
        operations_payload(
            safety_violations=1,
        )
    ).evaluate()

    assert report["status"] == "NOT_READY"
    assert any(
        item["code"]
        == "NO_SAFETY_VIOLATIONS"
        for item in report["blockers"]
    )


def test_readiness_gate_rejects_unsafe_center():
    payload = operations_payload()
    payload["financial_execution"] = True

    with pytest.raises(
        RuntimeError,
        match="financeira",
    ):
        gate_for(payload).evaluate()


def test_readiness_dashboard_is_safe_html():
    from app.api.routers.paper_readiness import (
        paper_readiness_dashboard,
    )

    response = asyncio.run(
        paper_readiness_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Readiness Paper" in body
    assert "Gate somente leitura" in body
    assert "Execução financeira bloqueada" in body
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_readiness_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_readiness as router_module,
    )

    expected = gate_for(
        operations_payload()
    ).evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    response = asyncio.run(
        router_module.paper_readiness_export_json()
    )

    payload = json.loads(
        response.body.decode("utf-8")
    )

    assert payload["status"] == "READY"
    assert payload["financial_execution"] is False
    assert (
        response.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_application_registers_readiness_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_readiness import (
        router,
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
        "/paper/readiness/health",
        "/paper/readiness/report",
        "/paper/readiness/dashboard",
        "/paper/readiness/export.json",
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
