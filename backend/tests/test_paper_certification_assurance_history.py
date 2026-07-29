from __future__ import annotations

import asyncio
import csv
import io

import pytest

from app.paper.certification_assurance_history import (
    PaperCertificationAssuranceHistory,
)


def snapshot(
    *,
    status="ASSURED",
    score=100,
):
    return {
        "status": status,
        "assured": status == "ASSURED",
        "scope": "PAPER_ONLY",
        "generated_at":
            "2026-07-28T12:00:00+00:00",
        "assurance_score": score,
        "summary": {
            "certification_status": "CERTIFIED",
            "certification_score": 100,
            "monitor_status": "HEALTHY",
            "monitor_score": 100,
            "chain_status": "VALID",
            "chain_valid": True,
            "evidence_entries": 5,
            "active_incidents": 0,
            "active_critical": 0,
            "active_warning": 0,
            "runtime_status": "STOPPED",
            "runtime_cycles": 3,
            "runtime_failures": 0,
        },
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
        PaperCertificationAssuranceHistory(
            tmp_path / "history.json"
        )
    )

    summary = history.summary()

    assert summary[
        "total_entries"
    ] == 0
    assert summary[
        "latest_status"
    ] is None
    assert summary[
        "live_authorization"
    ] is False


def test_capture_persists_snapshot(
    tmp_path,
):
    history = (
        PaperCertificationAssuranceHistory(
            tmp_path / "history.json"
        )
    )

    result = history.capture(
        snapshot()
    )

    assert result[
        "status"
    ] == "captured"
    assert result[
        "entry"
    ]["status"] == "ASSURED"
    assert history.summary()[
        "total_entries"
    ] == 1


def test_summary_calculates_streaks_and_transitions(
    tmp_path,
):
    history = (
        PaperCertificationAssuranceHistory(
            tmp_path / "history.json"
        )
    )

    history.capture(
        snapshot(
            status="PENDING",
            score=60,
        )
    )

    history.capture(
        snapshot(
            status="ASSURED",
            score=95,
        )
    )

    history.capture(
        snapshot(
            status="ASSURED",
            score=100,
        )
    )

    summary = history.summary()

    assert summary[
        "total_entries"
    ] == 3
    assert summary[
        "latest_status"
    ] == "ASSURED"
    assert summary[
        "current_streak"
    ] == 2
    assert summary[
        "longest_assured_streak"
    ] == 2
    assert summary[
        "transitions"
    ] == 1
    assert summary[
        "average_score"
    ] == pytest.approx(
        85.0
    )


def test_capture_rejects_live_authorization(
    tmp_path,
):
    history = (
        PaperCertificationAssuranceHistory(
            tmp_path / "history.json"
        )
    )

    unsafe = snapshot()
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


def test_dashboard_and_export_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_assurance_history
        as router_module,
    )

    history_path = (
        tmp_path / "history.json"
    )

    monkeypatch.setenv(
        "PAPER_ASSURANCE_HISTORY_PATH",
        str(history_path),
    )

    PaperCertificationAssuranceHistory(
        history_path
    ).capture(
        snapshot()
    )

    dashboard = asyncio.run(
        router_module
        .assurance_history_dashboard()
    )

    assert (
        "Histórico da Garantia Paper"
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
        .assurance_history_export_csv(
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
    assert rows[0]["status"] == (
        "ASSURED"
    )


def test_capture_endpoint_requires_confirmation(
    monkeypatch,
):
    from fastapi import HTTPException
    from app.api.routers import (
        paper_certification_assurance_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ):
        asyncio.run(
            router_module
            .assurance_history_capture(
                confirm="INVALID"
            )
        )


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_assurance_history import (
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
        "/paper/certification/assurance/history/health",
        "/paper/certification/assurance/history/summary",
        "/paper/certification/assurance/history/latest",
        "/paper/certification/assurance/history/entries",
        "/paper/certification/assurance/history/snapshot",
        "/paper/certification/assurance/history/capture",
        "/paper/certification/assurance/history/dashboard",
        "/paper/certification/assurance/history/export.csv",
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
        "/paper/certification/assurance/history/capture"
    ] == {"POST"}

    for path, method_set in (
        methods.items()
    ):
        if path != (
            "/paper/certification/assurance/history/capture"
        ):
            assert method_set == {"GET"}
