from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.final_paper_assurance_qualification_gate import (
    FinalPaperAssuranceGateCriteria,
    FinalPaperAssuranceQualificationGate,
)


def safe_flags(*, read_only=True):
    payload = {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }
    if read_only:
        payload["read_only"] = True
    return payload


class AssuranceStub:
    def __init__(self, status="ASSURED", score=100, **summary):
        self.payload = {
            "status": status,
            "assured": status == "ASSURED",
            "scope": "PAPER_ASSURANCE_ONLY",
            "assurance_score": score,
            "summary": {
                "integrity_status": "VALID",
                "monitor_status": "HEALTHY",
                "active_incidents": 0,
                "active_critical_incidents": 0,
                "component_errors": 0,
                "total_runtime_failures": 0,
                **summary,
            },
            "checks": [],
            "failures": [],
            **safe_flags(),
        }

    def evaluate(self):
        return self.payload


class HistoryStub:
    def __init__(
        self,
        total_entries=3,
        latest_status="ASSURED",
        latest_score=100,
        average_score=100,
        current_streak_status="ASSURED",
        current_streak=3,
    ):
        self.payload = {
            "total_entries": total_entries,
            "latest_status": latest_status,
            "latest_score": latest_score,
            "average_score": average_score,
            "current_streak_status": current_streak_status,
            "current_streak": current_streak,
            **safe_flags(),
        }

    def summary(self):
        return self.payload


class RuntimeStub:
    def __init__(self, failed_cycles=0):
        self.payload = {
            "status": "STOPPED",
            "failed_cycles": failed_cycles,
            "manual_start_required": True,
            **safe_flags(read_only=False),
        }

    def status(self):
        return self.payload


def gate(
    *,
    assurance=None,
    history=None,
    runtime=None,
):
    return FinalPaperAssuranceQualificationGate(
        assurance_provider=assurance or AssuranceStub(),
        history_factory=lambda: history or HistoryStub(),
        history_runtime=runtime or RuntimeStub(),
        criteria=FinalPaperAssuranceGateCriteria(
            min_history_entries=3,
            min_current_assured_streak=3,
            min_current_score=90,
            min_average_score=90,
            max_runtime_failures=0,
        ),
    )


def test_gate_returns_qualified():
    report = gate().evaluate()
    assert report["status"] == "QUALIFIED"
    assert report["qualified"] is True
    assert report["qualification_score"] == 100
    assert report["scope"] == "PAPER_ASSURANCE_QUALIFICATION_ONLY"
    assert report["next_step_authorized"] is False


def test_gate_returns_no_data():
    report = gate(
        assurance=AssuranceStub(status="NO_DATA", score=50),
        history=HistoryStub(
            total_entries=0,
            latest_status="NO_DATA",
            latest_score=0,
            average_score=0,
            current_streak_status="NO_DATA",
            current_streak=0,
        ),
    ).evaluate()
    assert report["status"] == "NO_DATA"
    assert report["qualified"] is False
    assert report["qualification_score"] <= 59


def test_gate_returns_pending_for_short_streak():
    report = gate(
        history=HistoryStub(current_streak=2),
    ).evaluate()
    assert report["status"] == "PENDING"
    assert report["qualification_score"] <= 79
    assert any(
        item["code"] == "CURRENT_ASSURED_STREAK"
        for item in report["failures"]
    )


def test_gate_blocks_critical_condition():
    report = gate(
        assurance=AssuranceStub(
            status="BLOCKED",
            score=40,
            integrity_status="BROKEN",
            monitor_status="CRITICAL",
            active_critical_incidents=1,
        ),
        history=HistoryStub(latest_status="BLOCKED", latest_score=40),
    ).evaluate()
    assert report["status"] == "BLOCKED"
    assert report["qualified"] is False
    assert report["qualification_score"] <= 49


def test_gate_warns_on_runtime_failure():
    report = gate(runtime=RuntimeStub(failed_cycles=1)).evaluate()
    assert report["status"] == "PENDING"
    assert report["summary"]["total_runtime_failures"] == 1


def test_gate_rejects_unsafe_component():
    unsafe = AssuranceStub()
    unsafe.payload["live_execution"] = True
    with pytest.raises(RuntimeError, match="final_assurance"):
        gate(assurance=unsafe).evaluate()


def test_dashboard_and_export_are_safe(monkeypatch):
    from app.api.routers import (
        paper_final_assurance_qualification_gate as router_module,
    )

    expected = gate().evaluate()
    monkeypatch.setattr(router_module, "_report", lambda: expected)

    dashboard = asyncio.run(
        router_module.final_assurance_qualification_gate_dashboard()
    )
    body = dashboard.body.decode("utf-8")
    assert "Gate de Qualificação Final Paper" in body
    assert "Não autoriza a próxima fase" in body
    assert dashboard.headers["x-predarb-next-step-authorization"] == "false"

    exported = asyncio.run(
        router_module.final_assurance_qualification_gate_export_json()
    )
    payload = json.loads(exported.body.decode("utf-8"))
    assert payload["status"] == "QUALIFIED"
    assert payload["next_step_authorized"] is False


def test_application_registers_gate_routes():
    from fastapi.routing import APIRoute, iter_route_contexts
    from app.api.routers.paper_final_assurance_qualification_gate import router
    from app.core.application import create_app

    app = create_app()
    paths = {
        context.path
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }
    required = {
        "/paper/final-assurance/qualification-gate/health",
        "/paper/final-assurance/qualification-gate/report",
        "/paper/final-assurance/qualification-gate/dashboard",
        "/paper/final-assurance/qualification-gate/export.json",
    }
    assert not (required - paths)
    methods = {
        route.path: set(route.methods or set())
        for route in router.routes
    }
    assert all(method_set == {"GET"} for method_set in methods.values())
