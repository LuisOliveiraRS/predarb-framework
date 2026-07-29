from __future__ import annotations

import csv
import json

import pytest

from app.paper.performance import (
    PaperPerformanceService,
)


def write_report(
    directory,
    *,
    name,
    status="PASS",
    cycles=5,
    successful=4,
    failed=1,
    no_signal=0,
    trades=6,
    equity_delta=2.65,
    return_rate=0.000265,
    drawdown_rate=0.0,
):
    payload = {
        "label": "test",
        "started_at": "2026-07-28T00:00:00+00:00",
        "finished_at": "2026-07-28T00:02:00+00:00",
        "actual_duration_seconds": 120,
        "summary": {
            "status": status,
            "samples": 13,
            "endpoint_errors": 0,
            "safety_violations": 0,
        },
        "performance": {
            "cycles_delta": cycles,
            "successful_cycles_delta": successful,
            "failed_cycles_delta": failed,
            "no_signal_cycles_delta": no_signal,
            "risk_stopped_cycles_delta": 0,
            "trade_count_delta": trades,
            "start_equity": 10000,
            "end_equity": 10000 + equity_delta,
            "equity_delta": equity_delta,
            "session_return_rate": return_rate,
            "max_drawdown": 0,
            "max_drawdown_rate": drawdown_rate,
        },
        "initial_sample": {
            "captured_at": "2026-07-28T00:00:00+00:00",
            "equity": 10000,
            "total_cycles": 0,
        },
        "final_sample": {
            "captured_at": "2026-07-28T00:02:00+00:00",
            "equity": 10000 + equity_delta,
            "total_cycles": cycles,
        },
        "execution_authorized": False,
        "live_execution": False,
    }

    path = directory / name
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )
    return path


def test_summary_is_safe_when_directory_is_empty(
    tmp_path,
):
    service = PaperPerformanceService(
        tmp_path
    )

    result = service.summary()

    assert result["total_reports"] == 0
    assert result["total_cycles"] == 0
    assert result["execution_authorized"] is False
    assert result["live_execution"] is False


def test_summary_consolidates_multiple_reports(
    tmp_path,
):
    write_report(
        tmp_path,
        name="phase8_long_session_001.json",
        cycles=5,
        successful=4,
        failed=1,
        trades=6,
        equity_delta=2.65,
    )

    write_report(
        tmp_path,
        name="phase8_long_session_002.json",
        cycles=10,
        successful=8,
        failed=0,
        no_signal=2,
        trades=12,
        equity_delta=5.0,
    )

    result = PaperPerformanceService(
        tmp_path
    ).summary()

    assert result["total_reports"] == 2
    assert result["passed_reports"] == 2
    assert result["total_cycles"] == 15
    assert result["successful_cycles"] == 12
    assert result["failed_cycles"] == 1
    assert result["no_signal_cycles"] == 2
    assert result["total_trades"] == 18
    assert result["cumulative_equity_delta"] == 7.65


def test_report_name_blocks_path_traversal(
    tmp_path,
):
    service = PaperPerformanceService(
        tmp_path
    )

    with pytest.raises(ValueError):
        service.get_report(
            "../phase8_long_session_001.json"
        )


def test_history_reads_csv_points(
    tmp_path,
):
    report = write_report(
        tmp_path,
        name="phase8_long_session_history.json",
    )

    csv_path = report.with_suffix(".csv")

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "captured_at",
                "total_cycles",
                "equity",
                "runtime_running",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "captured_at":
                    "2026-07-28T00:01:00+00:00",
                "total_cycles": "3",
                "equity": "10001.5",
                "runtime_running": "true",
            }
        )

    points = PaperPerformanceService(
        tmp_path
    ).history()

    assert len(points) == 1
    assert points[0]["total_cycles"] == 3.0
    assert points[0]["equity"] == 10001.5
    assert points[0]["runtime_running"] is True


def test_list_reports_marks_invalid_json(
    tmp_path,
):
    invalid = (
        tmp_path
        / "phase8_long_session_invalid.json"
    )
    invalid.write_text(
        "{invalid",
        encoding="utf-8",
    )

    records = PaperPerformanceService(
        tmp_path
    ).list_reports()

    assert records[0]["status"] == "INVALID"
    assert "error" in records[0]


def test_application_registers_performance_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.core.application import (
        create_app,
    )

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

    assert (
        "/paper/performance/summary"
        in paths
    )
    assert (
        "/paper/performance/reports"
        in paths
    )
    assert (
        "/paper/performance/history"
        in paths
    )
