from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest

from app.paper.final_paper_operational_assurance_history import (
    FinalPaperOperationalAssuranceHistory,
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


def report(
    *,
    status="ASSURED",
    score=100,
):
    return {
        "status": status,
        "assured": status == "ASSURED",
        "scope": "PAPER_ASSURANCE_ONLY",
        "generated_at": (
            "2026-07-28T12:00:00+00:00"
        ),
        "assurance_score": score,
        "summary": {
            "total_checks": 10,
            "passed_checks": (
                10
                if status == "ASSURED"
                else 7
            ),
            "failed_checks": (
                0
                if status == "ASSURED"
                else 3
            ),
            "critical_failures": (
                1
                if status == "BLOCKED"
                else 0
            ),
            "warning_failures": (
                1
                if status in {
                    "WARNING",
                    "NO_DATA",
                }
                else 0
            ),
            "component_errors": 0,
            "validation_status": (
                "PAPER_VALIDATED"
            ),
            "validation_score": 100,
            "validation_history_entries": 3,
            "evidence_entries": 2,
            "integrity_status": "VALID",
            "monitor_status": (
                "HEALTHY"
                if status == "ASSURED"
                else "WARNING"
            ),
            "monitor_score": (
                100
                if status == "ASSURED"
                else 79
            ),
            "active_incidents": (
                0
                if status == "ASSURED"
                else 1
            ),
            "active_critical_incidents": (
                1
                if status == "BLOCKED"
                else 0
            ),
            "validation_runtime_status": (
                "STOPPED"
            ),
            "incident_runtime_status": (
                "STOPPED"
            ),
            "total_runtime_failures": (
                0
                if status == "ASSURED"
                else 1
            ),
        },
        "checks": [],
        "failures": (
            []
            if status == "ASSURED"
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
        FinalPaperOperationalAssuranceHistory(
            tmp_path
            / "assurance_history.json"
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 0
    assert summary["latest_status"] is None
    assert (
        summary["next_step_authorized"]
        is False
    )


def test_capture_persists_entry(tmp_path):
    history = (
        FinalPaperOperationalAssuranceHistory(
            tmp_path
            / "assurance_history.json"
        )
    )

    captured = history.capture(
        report()
    )

    assert (
        captured["status"]
        == "captured"
    )
    assert (
        captured["entry"]["status"]
        == "ASSURED"
    )
    assert (
        captured["entry"]["scope"]
        == "PAPER_ASSURANCE_ONLY"
    )
    assert (
        captured["summary"]["total_entries"]
        == 1
    )


def test_summary_tracks_streaks_and_transitions(
    tmp_path,
):
    history = (
        FinalPaperOperationalAssuranceHistory(
            tmp_path
            / "assurance_history.json"
        )
    )

    history.capture(
        report(
            status="ASSURED",
            score=100,
        )
    )
    history.capture(
        report(
            status="WARNING",
            score=75,
        )
    )
    history.capture(
        report(
            status="ASSURED",
            score=95,
        )
    )
    history.capture(
        report(
            status="ASSURED",
            score=97,
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 4
    assert summary["latest_status"] == "ASSURED"
    assert summary["current_streak_status"] == "ASSURED"
    assert summary["current_streak"] == 2
    assert summary["longest_assured_streak"] == 2
    assert summary["transitions"] == 2
    assert summary["status_counts"]["ASSURED"] == 3


def test_max_entries_truncates_oldest(tmp_path):
    history = (
        FinalPaperOperationalAssuranceHistory(
            tmp_path
            / "assurance_history.json",
            max_entries=2,
        )
    )

    history.capture(
        report(
            status="ASSURED",
            score=100,
        )
    )
    history.capture(
        report(
            status="WARNING",
            score=75,
        )
    )
    history.capture(
        report(
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
        "WARNING",
        "BLOCKED",
    }


def test_capture_rejects_unsafe_report(
    tmp_path,
):
    history = (
        FinalPaperOperationalAssuranceHistory(
            tmp_path
            / "assurance_history.json"
        )
    )

    unsafe = report()
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
        paper_final_operational_assurance_history
        as router_module,
    )

    path = (
        tmp_path
        / "assurance_history.json"
    )

    monkeypatch.setenv(
        "PAPER_FINAL_ASSURANCE_HISTORY_PATH",
        str(path),
    )

    FinalPaperOperationalAssuranceHistory(
        path
    ).capture(
        report()
    )

    dashboard = asyncio.run(
        router_module
        .final_assurance_history_dashboard()
    )

    body = dashboard.body.decode(
        "utf-8"
    )

    assert (
        "Histórico da Garantia Final Paper"
        in body
    )
    assert (
        "CAPTURE-FINAL-PAPER-ASSURANCE"
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
        .final_assurance_history_export_csv(
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
    assert rows[0]["status"] == "ASSURED"

    json_response = asyncio.run(
        router_module
        .final_assurance_history_export_json()
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
        paper_final_operational_assurance_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        asyncio.run(
            router_module
            .final_assurance_history_capture(
                confirm="INVALID"
            )
        )

    assert (
        exc.value.status_code
        == 400
    )


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_operational_assurance_history import (
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
        "/paper/final-assurance/history/health",
        "/paper/final-assurance/history/summary",
        "/paper/final-assurance/history/latest",
        "/paper/final-assurance/history/entries",
        "/paper/final-assurance/history/snapshot",
        "/paper/final-assurance/history/capture",
        "/paper/final-assurance/history/dashboard",
        "/paper/final-assurance/history/export.csv",
        "/paper/final-assurance/history/export.json",
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
        "/paper/final-assurance/history/capture"
    ] == {"POST"}

    for path, method_set in methods.items():
        if (
            path
            != "/paper/final-assurance/history/capture"
        ):
            assert method_set == {"GET"}
