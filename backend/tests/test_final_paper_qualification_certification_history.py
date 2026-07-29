from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest

from app.paper.final_paper_qualification_certification_history import (
    FinalPaperQualificationCertificationHistory,
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


def certification_report(
    *,
    status="CERTIFIED",
    score=100,
):
    return {
        "status": status,
        "certified": (
            status == "CERTIFIED"
        ),
        "scope": (
            "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
        ),
        "generated_at": (
            "2026-07-28T12:00:00+00:00"
        ),
        "certification_score": score,
        "criteria": {
            "min_gate_history_entries": 3,
            "min_qualified_streak": 3,
            "min_current_gate_score": 90,
            "min_average_gate_score": 90,
            "max_gate_runtime_failures": 0,
        },
        "summary": {
            "total_checks": 10,
            "passed_checks": (
                10
                if status == "CERTIFIED"
                else 7
            ),
            "failed_checks": (
                0
                if status == "CERTIFIED"
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
                    "PENDING",
                    "NO_DATA",
                }
                else 0
            ),
            "gate_status": (
                "QUALIFIED"
                if status
                in {
                    "CERTIFIED",
                    "PENDING",
                }
                else "BLOCKED"
            ),
            "gate_score": (
                100
                if status == "CERTIFIED"
                else 75
            ),
            "gate_history_entries": 3,
            "latest_gate_status": (
                "QUALIFIED"
            ),
            "latest_gate_score": 100,
            "average_gate_score": 100,
            "current_streak_status": (
                "QUALIFIED"
            ),
            "current_streak": 3,
            "longest_qualified_streak": 3,
            "gate_runtime_status": (
                "STOPPED"
            ),
            "gate_runtime_running": False,
            "gate_runtime_failures": (
                0
                if status == "CERTIFIED"
                else 1
            ),
            "gate_critical_failures": (
                1
                if status == "BLOCKED"
                else 0
            ),
        },
        "checks": [],
        "failures": (
            []
            if status == "CERTIFIED"
            else [
                {
                    "code": "GATE_RUNTIME_FAILURES",
                }
            ]
        ),
        **safe_flags(),
    }


def test_empty_history_is_safe(tmp_path):
    history = (
        FinalPaperQualificationCertificationHistory(
            tmp_path
            / "certification_history.json"
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 0
    assert summary["latest_status"] is None
    assert (
        summary["next_step_authorized"]
        is False
    )


def test_capture_persists_certification_entry(
    tmp_path,
):
    history = (
        FinalPaperQualificationCertificationHistory(
            tmp_path
            / "certification_history.json"
        )
    )

    captured = history.capture(
        certification_report()
    )

    assert captured["status"] == "captured"
    assert (
        captured["entry"]["status"]
        == "CERTIFIED"
    )
    assert (
        captured["entry"]["scope"]
        == (
            "PAPER_QUALIFICATION_"
            "CERTIFICATION_ONLY"
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
        FinalPaperQualificationCertificationHistory(
            tmp_path
            / "certification_history.json"
        )
    )

    history.capture(
        certification_report(
            status="CERTIFIED",
            score=100,
        )
    )
    history.capture(
        certification_report(
            status="PENDING",
            score=75,
        )
    )
    history.capture(
        certification_report(
            status="CERTIFIED",
            score=95,
        )
    )
    history.capture(
        certification_report(
            status="CERTIFIED",
            score=97,
        )
    )

    summary = history.summary()

    assert summary["total_entries"] == 4
    assert summary["latest_status"] == "CERTIFIED"
    assert (
        summary["current_streak_status"]
        == "CERTIFIED"
    )
    assert summary["current_streak"] == 2
    assert (
        summary["longest_certified_streak"]
        == 2
    )
    assert summary["transitions"] == 2
    assert (
        summary["status_counts"]["CERTIFIED"]
        == 3
    )


def test_max_entries_truncates_oldest(
    tmp_path,
):
    history = (
        FinalPaperQualificationCertificationHistory(
            tmp_path
            / "certification_history.json",
            max_entries=2,
        )
    )

    history.capture(
        certification_report(
            status="CERTIFIED",
            score=100,
        )
    )
    history.capture(
        certification_report(
            status="PENDING",
            score=75,
        )
    )
    history.capture(
        certification_report(
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


def test_capture_rejects_unsafe_report(
    tmp_path,
):
    history = (
        FinalPaperQualificationCertificationHistory(
            tmp_path
            / "certification_history.json"
        )
    )

    unsafe = certification_report()
    unsafe[
        "next_step_authorized"
    ] = True

    with pytest.raises(
        ValueError,
        match="next_step_authorized",
    ):
        history.capture(unsafe)


def test_dashboard_and_exports_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_final_qualification_certification_history
        as router_module,
    )

    path = (
        tmp_path
        / "certification_history.json"
    )

    monkeypatch.setenv(
        "PAPER_FINAL_QUALIFICATION_CERTIFICATION_HISTORY_PATH",
        str(path),
    )

    FinalPaperQualificationCertificationHistory(
        path
    ).capture(
        certification_report()
    )

    dashboard = asyncio.run(
        router_module
        .qualification_certification_history_dashboard()
    )

    body = dashboard.body.decode(
        "utf-8"
    )

    assert (
        "Histórico da Certificação Final Paper"
        in body
    )
    assert (
        "CAPTURE-FINAL-PAPER-QUALIFICATION-CERTIFICATION"
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
        .qualification_certification_history_export_csv(
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
    assert rows[0]["status"] == "CERTIFIED"

    json_response = asyncio.run(
        router_module
        .qualification_certification_history_export_json()
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
        paper_final_qualification_certification_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        asyncio.run(
            router_module
            .qualification_certification_history_capture(
                confirm="INVALID"
            )
        )

    assert exc.value.status_code == 400


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_qualification_certification_history import (
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
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/health"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/summary"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/latest"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/entries"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/snapshot"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/capture"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/dashboard"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/export.csv"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/"
            "history/export.json"
        ),
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

    capture_path = (
        "/paper/final-assurance/"
        "qualification-certification/"
        "history/capture"
    )

    assert methods[
        capture_path
    ] == {"POST"}

    for path, method_set in methods.items():
        if path != capture_path:
            assert method_set == {"GET"}
