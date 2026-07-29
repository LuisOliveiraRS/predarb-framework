from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest

from app.paper.final_paper_assurance_qualification_gate_history import (
    FinalPaperAssuranceQualificationGateHistory,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


def gate_report(
    *,
    status="QUALIFIED",
    score=100,
):
    return {
        "status": status,
        "qualified": (
            status == "QUALIFIED"
        ),
        "scope": (
            "PAPER_ASSURANCE_QUALIFICATION_ONLY"
        ),
        "generated_at": (
            "2026-07-28T12:00:00+00:00"
        ),
        "qualification_score": score,
        "criteria": {
            "min_history_entries": 3,
            "min_current_assured_streak": 3,
            "min_current_score": 90,
            "min_average_score": 90,
            "max_runtime_failures": 0,
        },
        "summary": {
            "total_checks": 14,
            "passed_checks": (
                14
                if status == "QUALIFIED"
                else 10
            ),
            "failed_checks": (
                0
                if status == "QUALIFIED"
                else 4
            ),
            "critical_failures": (
                1
                if status == "BLOCKED"
                else 0
            ),
            "warning_failures": (
                1
                if status in {
                    "PENDING",
                    "NO_DATA",
                }
                else 0
            ),
            "assurance_status": (
                "ASSURED"
                if status
                in {
                    "QUALIFIED",
                    "PENDING",
                }
                else "WARNING"
            ),
            "assurance_score": 100,
            "history_entries": 3,
            "latest_history_status": (
                "ASSURED"
            ),
            "latest_history_score": 100,
            "average_history_score": 100,
            "current_streak_status": (
                "ASSURED"
            ),
            "current_streak": 3,
            "integrity_status": "VALID",
            "monitor_status": "HEALTHY",
            "active_incidents": (
                0
                if status != "BLOCKED"
                else 1
            ),
            "active_critical_incidents": (
                1
                if status == "BLOCKED"
                else 0
            ),
            "component_errors": 0,
            "total_runtime_failures": (
                0
                if status == "QUALIFIED"
                else 1
            ),
            "history_runtime_status": (
                "STOPPED"
            ),
        },
        "checks": [],
        "failures": (
            []
            if status == "QUALIFIED"
            else [
                {
                    "code": "RUNTIME_FAILURES",
                }
            ]
        ),
        **safe_flags(),
    }


def test_empty_history_is_safe(tmp_path):
    history = (
        FinalPaperAssuranceQualificationGateHistory(
            tmp_path
            / "gate_history.json"
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 0
    assert summary["latest_status"] is None
    assert (
        summary["next_step_authorized"]
        is False
    )


def test_capture_persists_gate_entry(tmp_path):
    history = (
        FinalPaperAssuranceQualificationGateHistory(
            tmp_path
            / "gate_history.json"
        )
    )

    captured = history.capture(
        gate_report()
    )

    assert (
        captured["status"]
        == "captured"
    )
    assert (
        captured["entry"]["status"]
        == "QUALIFIED"
    )
    assert (
        captured["entry"]["scope"]
        == (
            "PAPER_ASSURANCE_QUALIFICATION_ONLY"
        )
    )
    assert (
        captured["summary"]["total_entries"]
        == 1
    )


def test_summary_tracks_streaks_and_transitions(
    tmp_path,
):
    history = (
        FinalPaperAssuranceQualificationGateHistory(
            tmp_path
            / "gate_history.json"
        )
    )

    history.capture(
        gate_report(
            status="QUALIFIED",
            score=100,
        )
    )
    history.capture(
        gate_report(
            status="PENDING",
            score=75,
        )
    )
    history.capture(
        gate_report(
            status="QUALIFIED",
            score=95,
        )
    )
    history.capture(
        gate_report(
            status="QUALIFIED",
            score=97,
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 4
    assert summary["latest_status"] == "QUALIFIED"
    assert (
        summary["current_streak_status"]
        == "QUALIFIED"
    )
    assert summary["current_streak"] == 2
    assert (
        summary["longest_qualified_streak"]
        == 2
    )
    assert summary["transitions"] == 2
    assert (
        summary["status_counts"]["QUALIFIED"]
        == 3
    )


def test_max_entries_truncates_oldest(tmp_path):
    history = (
        FinalPaperAssuranceQualificationGateHistory(
            tmp_path
            / "gate_history.json",
            max_entries=2,
        )
    )

    history.capture(
        gate_report(
            status="QUALIFIED",
            score=100,
        )
    )
    history.capture(
        gate_report(
            status="PENDING",
            score=75,
        )
    )
    history.capture(
        gate_report(
            status="BLOCKED",
            score=40,
        )
    )

    entries = history.list_entries(
        limit=10
    )

    assert len(entries) == 2
    assert {
        item["status"]
        for item in entries
    } == {
        "PENDING",
        "BLOCKED",
    }


def test_capture_rejects_unsafe_gate_report(
    tmp_path,
):
    history = (
        FinalPaperAssuranceQualificationGateHistory(
            tmp_path
            / "gate_history.json"
        )
    )

    unsafe = gate_report()
    unsafe[
        "next_step_authorized"
    ] = True

    with pytest.raises(
        ValueError,
        match="next_step_authorized",
    ):
        history.capture(
            unsafe
        )


def test_dashboard_and_exports_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_final_assurance_qualification_gate_history
        as router_module,
    )

    path = (
        tmp_path
        / "gate_history.json"
    )

    monkeypatch.setenv(
        "PAPER_FINAL_ASSURANCE_GATE_HISTORY_PATH",
        str(path),
    )

    FinalPaperAssuranceQualificationGateHistory(
        path
    ).capture(
        gate_report()
    )

    dashboard = asyncio.run(
        router_module
        .qualification_gate_history_dashboard()
    )

    body = dashboard.body.decode(
        "utf-8"
    )

    assert (
        "Histórico do Gate de Qualificação"
        in body
    )
    assert (
        "CAPTURE-FINAL-PAPER-ASSURANCE-QUALIFICATION-GATE"
        in body
    )
    assert (
        dashboard.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )

    csv_response = asyncio.run(
        router_module
        .qualification_gate_history_export_csv(
            limit=5000
        )
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                csv_response.body.decode(
                    "utf-8-sig"
                )
            )
        )
    )

    assert len(rows) == 1
    assert (
        rows[0]["status"]
        == "QUALIFIED"
    )

    json_response = asyncio.run(
        router_module
        .qualification_gate_history_export_json()
    )

    payload = json.loads(
        json_response.body.decode(
            "utf-8"
        )
    )

    assert (
        payload["summary"]["total_entries"]
        == 1
    )
    assert (
        payload["next_step_authorized"]
        is False
    )


def test_capture_endpoint_requires_confirmation():
    from fastapi import HTTPException
    from app.api.routers import (
        paper_final_assurance_qualification_gate_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        asyncio.run(
            router_module
            .qualification_gate_history_capture(
                confirm="INVALID"
            )
        )

    assert (
        exc.value.status_code
        == 400
    )


def test_application_registers_gate_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_assurance_qualification_gate_history import (
        router,
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
        "/paper/final-assurance/qualification-gate/history/health",
        "/paper/final-assurance/qualification-gate/history/summary",
        "/paper/final-assurance/qualification-gate/history/latest",
        "/paper/final-assurance/qualification-gate/history/entries",
        "/paper/final-assurance/qualification-gate/history/snapshot",
        "/paper/final-assurance/qualification-gate/history/capture",
        "/paper/final-assurance/qualification-gate/history/dashboard",
        "/paper/final-assurance/qualification-gate/history/export.csv",
        "/paper/final-assurance/qualification-gate/history/export.json",
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

    assert methods[
        "/paper/final-assurance/qualification-gate/history/capture"
    ] == {"POST"}

    for path, method_set in methods.items():
        if (
            path
            != (
                "/paper/final-assurance/"
                "qualification-gate/history/capture"
            )
        ):
            assert method_set == {"GET"}
