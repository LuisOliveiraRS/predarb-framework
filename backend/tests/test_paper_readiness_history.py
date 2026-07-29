from __future__ import annotations

import asyncio
import csv
import io

import pytest

from app.paper.readiness_history import (
    PaperReadinessHistory,
)


def readiness_report(
    *,
    status="READY",
    score=90,
    blockers=0,
    warnings=0,
    insufficient=0,
):
    return {
        "status": status,
        "ready": status == "READY",
        "generated_at":
            "2026-07-28T12:00:00+00:00",
        "readiness_score": score,
        "thresholds": {
            "min_reports": 2,
        },
        "summary": {
            "passed_checks": (
                11
                - blockers
                - warnings
                - insufficient
            ),
            "blockers": blockers,
            "warnings": warnings,
            "insufficient_data": insufficient,
        },
        "blockers": [],
        "warnings": [],
        "insufficient_data": [],
        "operations_status": "HEALTHY",
        "manual_start_required": True,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def test_empty_history_is_safe(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    summary = history.summary()

    assert summary["total_entries"] == 0
    assert summary["latest_status"] is None
    assert summary["execution_authorized"] is False
    assert summary["live_execution"] is False
    assert summary["financial_execution"] is False


def test_capture_persists_readiness_entry(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    result = history.capture(
        readiness_report()
    )

    assert result["status"] == "captured"
    assert result["entry"]["status"] == "READY"
    assert result["entry"][
        "readiness_score"
    ] == 90
    assert history.summary()[
        "total_entries"
    ] == 1


def test_capture_calculates_score_delta(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    history.capture(
        readiness_report(score=70)
    )

    second = history.capture(
        readiness_report(score=85)
    )

    assert second["entry"][
        "score_delta"
    ] == 15


def test_summary_calculates_streaks(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    history.capture(
        readiness_report(
            status="INSUFFICIENT_DATA",
            score=60,
            insufficient=2,
        )
    )

    history.capture(
        readiness_report(
            status="READY",
            score=90,
        )
    )

    history.capture(
        readiness_report(
            status="READY",
            score=92,
        )
    )

    summary = history.summary()

    assert summary["current_status"] == "READY"
    assert summary["current_streak"] == 2
    assert summary[
        "longest_ready_streak"
    ] == 2
    assert summary[
        "status_transitions"
    ] == 1


def test_history_rejects_unsafe_report(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    unsafe = readiness_report()
    unsafe["financial_execution"] = True

    with pytest.raises(
        ValueError,
        match="financeira",
    ):
        history.capture(unsafe)


def test_history_filters_status(
    tmp_path,
):
    history = PaperReadinessHistory(
        tmp_path / "history.json"
    )

    history.capture(
        readiness_report(
            status="READY",
            score=90,
        )
    )

    history.capture(
        readiness_report(
            status="NOT_READY",
            score=50,
            blockers=2,
        )
    )

    ready = history.list_entries(
        status="READY"
    )

    assert len(ready) == 1
    assert ready[0]["status"] == "READY"


def test_history_dashboard_and_export_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_readiness_history as router_module,
    )

    history_path = tmp_path / "history.json"

    monkeypatch.setenv(
        "PAPER_READINESS_HISTORY_PATH",
        str(history_path),
    )

    PaperReadinessHistory(
        history_path
    ).capture(
        readiness_report()
    )

    dashboard = asyncio.run(
        router_module
        .readiness_history_dashboard()
    )

    assert (
        "Histórico de Readiness"
        in dashboard.body.decode("utf-8")
    )

    assert (
        dashboard.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )

    export = asyncio.run(
        router_module
        .readiness_history_export_csv(
            limit=5000
        )
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                export.body.decode(
                    "utf-8-sig"
                )
            )
        )
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "READY"
    assert (
        export.headers[
            "x-predarb-financial-execution"
        ]
        == "false"
    )


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_readiness_history import (
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
        "/paper/readiness/history/health",
        "/paper/readiness/history/summary",
        "/paper/readiness/history/latest",
        "/paper/readiness/history/entries",
        "/paper/readiness/history/snapshot",
        "/paper/readiness/history/capture",
        "/paper/readiness/history/dashboard",
        "/paper/readiness/history/export.csv",
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
        "/paper/readiness/history/capture"
    ] == {"POST"}

    for path, method_set in methods.items():
        if path != (
            "/paper/readiness/history/capture"
        ):
            assert method_set == {"GET"}
