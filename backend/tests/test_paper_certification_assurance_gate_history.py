from __future__ import annotations

import asyncio
import csv
import io

import pytest

from app.paper.certification_assurance_gate_history import (
    PaperAssuranceQualificationHistory,
)


def report(
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
            "PAPER_ASSURANCE_ONLY"
        ),
        "generated_at": (
            "2026-07-28T12:00:00+00:00"
        ),
        "qualification_score": score,
        "thresholds": {
            "min_entries": 5,
        },
        "summary": {
            "total_checks": 10,
            "passed_checks": (
                10
                if status == "QUALIFIED"
                else 7
            ),
            "failed_checks": (
                0
                if status == "QUALIFIED"
                else 3
            ),
            "failed_data_checks": (
                0
            ),
            "failed_qualification_checks": (
                0
                if status == "QUALIFIED"
                else 3
            ),
            "total_history_entries": 5,
            "recent_entries": 5,
            "latest_status": "ASSURED",
            "latest_score": 96,
            "recent_average_score": 93,
            "assured_streak": 3,
            "recent_warning": 0,
            "recent_blocked": 0,
            "recent_critical": 0,
        },
        "checks": [],
        "failures": (
            []
            if status == "QUALIFIED"
            else [
                {
                    "code": "LATEST_SCORE",
                }
            ]
        ),
        "manual_start_required": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


def test_empty_history_is_safe(
    tmp_path,
):
    history = (
        PaperAssuranceQualificationHistory(
            tmp_path / "history.json"
        )
    )

    summary = history.summary()

    assert (
        summary["total_entries"]
        == 0
    )

    assert (
        summary["latest_status"]
        is None
    )

    assert (
        summary[
            "live_authorization"
        ]
        is False
    )


def test_capture_persists_report(
    tmp_path,
):
    history = (
        PaperAssuranceQualificationHistory(
            tmp_path / "history.json"
        )
    )

    result = history.capture(
        report()
    )

    assert (
        result["status"]
        == "captured"
    )

    assert (
        result["entry"]["status"]
        == "QUALIFIED"
    )

    assert (
        history.summary()[
            "total_entries"
        ]
        == 1
    )


def test_summary_calculates_streaks_and_transitions(
    tmp_path,
):
    history = (
        PaperAssuranceQualificationHistory(
            tmp_path / "history.json"
        )
    )

    history.capture(
        report(
            status="INSUFFICIENT_DATA",
            score=60,
        )
    )

    history.capture(
        report(
            status="QUALIFIED",
            score=95,
        )
    )

    history.capture(
        report(
            status="QUALIFIED",
            score=100,
        )
    )

    summary = history.summary()

    assert (
        summary["total_entries"]
        == 3
    )

    assert (
        summary["latest_status"]
        == "QUALIFIED"
    )

    assert (
        summary["current_streak"]
        == 2
    )

    assert (
        summary[
            "longest_qualified_streak"
        ]
        == 2
    )

    assert (
        summary["transitions"]
        == 1
    )

    assert (
        summary["average_score"]
        == pytest.approx(
            85.0
        )
    )


def test_capture_rejects_live_authorization(
    tmp_path,
):
    history = (
        PaperAssuranceQualificationHistory(
            tmp_path / "history.json"
        )
    )

    unsafe = report()

    unsafe[
        "live_authorization"
    ] = True

    with pytest.raises(
        ValueError,
        match="live_authorization",
    ):
        history.capture(
            unsafe
        )


def test_capture_keeps_failure_codes(
    tmp_path,
):
    history = (
        PaperAssuranceQualificationHistory(
            tmp_path / "history.json"
        )
    )

    result = history.capture(
        report(
            status="NOT_QUALIFIED",
            score=70,
        )
    )

    assert (
        result["entry"][
            "failure_codes"
        ]
        == ["LATEST_SCORE"]
    )


def test_dashboard_and_export_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_assurance_gate_history
        as router_module,
    )

    history_path = (
        tmp_path / "history.json"
    )

    monkeypatch.setenv(
        "PAPER_ASSURANCE_GATE_HISTORY_PATH",
        str(history_path),
    )

    PaperAssuranceQualificationHistory(
        history_path
    ).capture(
        report()
    )

    dashboard = asyncio.run(
        router_module
        .assurance_gate_history_dashboard()
    )

    assert (
        "Histórico do Gate de Qualificação"
        in dashboard.body.decode(
            "utf-8"
        )
    )

    assert (
        dashboard.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )

    response = asyncio.run(
        router_module
        .assurance_gate_history_export_csv(
            limit=5000
        )
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                response.body.decode(
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


def test_capture_endpoint_requires_confirmation():
    from fastapi import (
        HTTPException,
    )
    from app.api.routers import (
        paper_certification_assurance_gate_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ):
        asyncio.run(
            router_module
            .assurance_gate_history_capture(
                confirm="INVALID"
            )
        )


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_assurance_gate_history import (
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
        "/paper/certification/assurance/gate/history/health",
        "/paper/certification/assurance/gate/history/summary",
        "/paper/certification/assurance/gate/history/latest",
        "/paper/certification/assurance/gate/history/entries",
        "/paper/certification/assurance/gate/history/snapshot",
        "/paper/certification/assurance/gate/history/capture",
        "/paper/certification/assurance/gate/history/dashboard",
        "/paper/certification/assurance/gate/history/export.csv",
    }

    assert not (
        required - paths
    )

    methods = {
        route.path: set(
            route.methods
            or set()
        )
        for route in router.routes
    }

    assert (
        methods[
            "/paper/certification/assurance/gate/history/capture"
        ]
        == {"POST"}
    )

    for path, method_set in (
        methods.items()
    ):
        if path != (
            "/paper/certification/assurance/gate/history/capture"
        ):
            assert (
                method_set
                == {"GET"}
            )
