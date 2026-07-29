from __future__ import annotations

import asyncio
import csv
import io

import pytest

from app.paper.final_paper_validation_history import (
    FinalPaperValidationHistory,
)


def report(
    *,
    status="PAPER_VALIDATED",
    score=100,
):
    return {
        "status": status,
        "validated": (
            status
            == "PAPER_VALIDATED"
        ),
        "scope": (
            "PAPER_VALIDATION_ONLY"
        ),
        "generated_at": (
            "2026-07-28T12:00:00+00:00"
        ),
        "validation_score": score,
        "thresholds": {
            "min_gate_evaluations": 3,
        },
        "summary": {
            "total_checks": 9,
            "passed_checks": (
                9
                if status
                == "PAPER_VALIDATED"
                else 6
            ),
            "failed_checks": (
                0
                if status
                == "PAPER_VALIDATED"
                else 3
            ),
            "failed_data_checks": 0,
            "failed_validation_checks": (
                0
                if status
                == "PAPER_VALIDATED"
                else 3
            ),
            "assurance_status": "ASSURED",
            "assurance_score": 100,
            "gate_status": "QUALIFIED",
            "gate_score": 100,
            "gate_history_entries": 3,
            "gate_history_latest_status": (
                "QUALIFIED"
            ),
            "qualified_streak": 3,
            "assurance_runtime_status": (
                "STOPPED"
            ),
            "gate_runtime_status": (
                "STOPPED"
            ),
            "assurance_runtime_failures": 0,
            "gate_runtime_failures": 0,
            "total_runtime_failures": 0,
        },
        "checks": [],
        "failures": (
            []
            if status
            == "PAPER_VALIDATED"
            else [
                {
                    "code":
                        "QUALIFIED_STREAK",
                }
            ]
        ),
        "manual_start_required": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


def test_empty_history_is_safe(
    tmp_path,
):
    history = (
        FinalPaperValidationHistory(
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

    assert (
        summary[
            "next_step_authorized"
        ]
        is False
    )


def test_capture_persists_report(
    tmp_path,
):
    history = (
        FinalPaperValidationHistory(
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
        == "PAPER_VALIDATED"
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
        FinalPaperValidationHistory(
            tmp_path / "history.json"
        )
    )

    history.capture(
        report(
            status="PAPER_PENDING",
            score=70,
        )
    )

    history.capture(
        report(
            status="PAPER_VALIDATED",
            score=95,
        )
    )

    history.capture(
        report(
            status="PAPER_VALIDATED",
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
        == "PAPER_VALIDATED"
    )

    assert (
        summary["current_streak"]
        == 2
    )

    assert (
        summary[
            "longest_validated_streak"
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
            88.3333333333
        )
    )


def test_capture_rejects_next_step_authorization(
    tmp_path,
):
    history = (
        FinalPaperValidationHistory(
            tmp_path / "history.json"
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


def test_load_rejects_unsafe_persisted_state(
    tmp_path,
):
    path = (
        tmp_path / "history.json"
    )

    path.write_text(
        """{
          "version": 1,
          "updated_at": null,
          "entries": [],
          "paper_execution_authorized": false,
          "live_authorization": true,
          "execution_authorized": false,
          "live_execution": false,
          "financial_execution": false,
          "next_step_authorized": false,
          "read_only": true
        }""",
        encoding="utf-8",
    )

    with pytest.raises(
        ValueError,
        match="live_authorization",
    ):
        FinalPaperValidationHistory(
            path
        ).load()


def test_dashboard_and_export_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_final_validation_history
        as router_module,
    )

    history_path = (
        tmp_path / "history.json"
    )

    monkeypatch.setenv(
        "PAPER_FINAL_VALIDATION_HISTORY_PATH",
        str(history_path),
    )

    FinalPaperValidationHistory(
        history_path
    ).capture(
        report()
    )

    dashboard = asyncio.run(
        router_module
        .final_validation_history_dashboard()
    )

    assert (
        "Histórico da Validação Final Paper"
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

    assert (
        dashboard.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )

    response = asyncio.run(
        router_module
        .final_validation_history_export_csv(
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
        == "PAPER_VALIDATED"
    )


def test_capture_endpoint_requires_confirmation():
    from fastapi import (
        HTTPException,
    )
    from app.api.routers import (
        paper_final_validation_history
        as router_module,
    )

    with pytest.raises(
        HTTPException,
    ):
        asyncio.run(
            router_module
            .final_validation_history_capture(
                confirm="INVALID"
            )
        )


def test_application_registers_history_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_validation_history import (
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
        "/paper/final-validation/history/health",
        "/paper/final-validation/history/summary",
        "/paper/final-validation/history/latest",
        "/paper/final-validation/history/entries",
        "/paper/final-validation/history/snapshot",
        "/paper/final-validation/history/capture",
        "/paper/final-validation/history/dashboard",
        "/paper/final-validation/history/export.csv",
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
            "/paper/final-validation/history/capture"
        ]
        == {"POST"}
    )

    for path, method_set in (
        methods.items()
    ):
        if path != (
            "/paper/final-validation/history/capture"
        ):
            assert (
                method_set
                == {"GET"}
            )
