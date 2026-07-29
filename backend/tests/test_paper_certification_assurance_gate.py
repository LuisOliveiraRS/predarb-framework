from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.certification_assurance_gate import (
    AssuranceGateThresholds,
    PaperAssuranceQualificationGate,
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


def entry(
    status="ASSURED",
    score=95,
):
    return {
        "id": f"{status}-{score}",
        "captured_at":
            "2026-07-28T12:00:00+00:00",
        "status": status,
        "assurance_score": score,
        **safe_flags(),
    }


class HistoryStub:
    def __init__(
        self,
        entries,
    ):
        self.entries = entries

    def summary(self):
        return {
            "total_entries": len(
                self.entries
            ),
            **safe_flags(),
        }

    def list_entries(
        self,
        *,
        limit,
    ):
        return list(
            self.entries[:limit]
        )


def gate_for(entries):
    return PaperAssuranceQualificationGate(
        history=HistoryStub(entries),
        thresholds=AssuranceGateThresholds(
            min_entries=5,
            min_assured_streak=3,
            recent_window=5,
            min_latest_score=85,
            min_recent_average_score=80,
            max_recent_warning=1,
            max_recent_blocked=0,
            max_recent_critical=0,
        ),
    )


def test_gate_returns_insufficient_data():
    report = gate_for(
        [
            entry(),
            entry(),
        ]
    ).evaluate()

    assert (
        report["status"]
        == "INSUFFICIENT_DATA"
    )
    assert report["qualified"] is False
    assert report["scope"] == (
        "PAPER_ASSURANCE_ONLY"
    )


def test_gate_returns_not_qualified():
    entries = [
        entry("WARNING", 70),
        entry("ASSURED", 95),
        entry("ASSURED", 94),
        entry("ASSURED", 93),
        entry("ASSURED", 92),
    ]

    report = gate_for(
        entries
    ).evaluate()

    assert (
        report["status"]
        == "NOT_QUALIFIED"
    )
    assert report["qualified"] is False
    assert any(
        item["code"]
        == "LATEST_STATUS_ASSURED"
        for item in report["failures"]
    )


def test_gate_returns_qualified():
    entries = [
        entry("ASSURED", 96),
        entry("ASSURED", 95),
        entry("ASSURED", 94),
        entry("WARNING", 82),
        entry("ASSURED", 90),
    ]

    report = gate_for(
        entries
    ).evaluate()

    assert report["status"] == "QUALIFIED"
    assert report["qualified"] is True
    assert report["summary"][
        "assured_streak"
    ] == 3
    assert report["summary"][
        "recent_warning"
    ] == 1
    assert report[
        "live_authorization"
    ] is False


def test_gate_blocks_recent_critical():
    entries = [
        entry("ASSURED", 96),
        entry("ASSURED", 95),
        entry("ASSURED", 94),
        entry("CRITICAL", 40),
        entry("ASSURED", 90),
    ]

    report = gate_for(
        entries
    ).evaluate()

    assert (
        report["status"]
        == "NOT_QUALIFIED"
    )
    assert any(
        item["code"]
        == "RECENT_CRITICAL_LIMIT"
        for item in report["failures"]
    )


def test_gate_rejects_unsafe_history():
    unsafe = entry()
    unsafe["live_execution"] = True

    with pytest.raises(
        RuntimeError,
        match="history_entry",
    ):
        gate_for(
            [unsafe] * 5
        ).evaluate()


def test_dashboard_is_safe_html():
    from app.api.routers.paper_certification_assurance_gate import (
        assurance_gate_dashboard,
    )

    response = asyncio.run(
        assurance_gate_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert (
        "Gate de Qualificação Paper"
        in body
    )
    assert (
        "Não autoriza execução live"
        in body
    )
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_assurance_gate
        as router_module,
    )

    expected = gate_for(
        [
            entry("ASSURED", 96),
            entry("ASSURED", 95),
            entry("ASSURED", 94),
            entry("WARNING", 82),
            entry("ASSURED", 90),
        ]
    ).evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    response = asyncio.run(
        router_module
        .assurance_gate_export_json()
    )

    payload = json.loads(
        response.body.decode("utf-8")
    )

    assert payload["status"] == "QUALIFIED"
    assert payload["live_authorization"] is False
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_application_registers_gate_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_assurance_gate import (
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
        "/paper/certification/assurance/gate/health",
        "/paper/certification/assurance/gate/report",
        "/paper/certification/assurance/gate/dashboard",
        "/paper/certification/assurance/gate/export.json",
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
        method_set == {"GET"}
        for method_set in methods.values()
    )
