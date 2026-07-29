from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from app.paper.performance import (
    PaperPerformanceService,
)
from app.paper.performance_monitor import (
    MonitorThresholds,
    PaperPerformanceMonitor,
)


NOW = datetime(
    2026,
    7,
    28,
    12,
    0,
    tzinfo=timezone.utc,
)


def write_report(
    directory,
    *,
    name="phase8_long_session_monitor.json",
    finished_at="2026-07-28T11:00:00+00:00",
    status="PASS",
    cycles=10,
    successful=9,
    failed=1,
    no_signal=0,
    trades=8,
    drawdown_rate=0.01,
    endpoint_errors=0,
    safety_violations=0,
):
    payload = {
        "label": "monitor-test",
        "started_at":
            "2026-07-28T10:30:00+00:00",
        "finished_at": finished_at,
        "actual_duration_seconds": 1800,
        "summary": {
            "status": status,
            "samples": 10,
            "endpoint_errors": endpoint_errors,
            "safety_violations": (
                safety_violations
            ),
        },
        "performance": {
            "cycles_delta": cycles,
            "successful_cycles_delta": (
                successful
            ),
            "failed_cycles_delta": failed,
            "no_signal_cycles_delta": (
                no_signal
            ),
            "risk_stopped_cycles_delta": 0,
            "trade_count_delta": trades,
            "start_equity": 10000,
            "end_equity": 10005,
            "equity_delta": 5,
            "session_return_rate": 0.0005,
            "max_drawdown": 100,
            "max_drawdown_rate": (
                drawdown_rate
            ),
        },
        "execution_authorized": False,
        "live_execution": False,
    }

    path = directory / name
    path.write_text(
        json.dumps(payload),
        encoding="utf-8",
    )


def monitor_for(
    directory,
):
    service = PaperPerformanceService(
        directory
    )

    thresholds = MonitorThresholds(
        max_failed_cycle_rate=0.20,
        min_success_cycle_rate=0.60,
        max_drawdown_rate=0.05,
        stale_hours=24,
    )

    return PaperPerformanceMonitor(
        service=service,
        thresholds=thresholds,
        now=NOW,
    )


def test_monitor_reports_no_data_safely(
    tmp_path,
):
    snapshot = monitor_for(
        tmp_path
    ).snapshot()

    assert snapshot["status"] == "NO_DATA"
    assert snapshot["score"] < 100
    assert snapshot["live_execution"] is False
    assert snapshot["read_only"] is True
    assert any(
        item["code"] == "NO_REPORTS"
        for item in snapshot["alerts"]
    )


def test_monitor_is_healthy_for_good_session(
    tmp_path,
):
    write_report(tmp_path)

    snapshot = monitor_for(
        tmp_path
    ).snapshot()

    assert snapshot["status"] == "HEALTHY"
    assert snapshot["score"] >= 75
    assert snapshot["rates"][
        "success_cycle_rate"
    ] == 0.9
    assert snapshot["alert_counts"][
        "critical"
    ] == 0


def test_monitor_warns_on_failed_cycle_rate(
    tmp_path,
):
    write_report(
        tmp_path,
        cycles=10,
        successful=5,
        failed=4,
        no_signal=1,
    )

    snapshot = monitor_for(
        tmp_path
    ).snapshot()

    assert snapshot["status"] == "WARNING"
    assert any(
        item["code"]
        == "FAILED_CYCLE_RATE_HIGH"
        for item in snapshot["alerts"]
    )


def test_monitor_is_critical_on_safety_violation(
    tmp_path,
):
    write_report(
        tmp_path,
        safety_violations=1,
    )

    snapshot = monitor_for(
        tmp_path
    ).snapshot()

    assert snapshot["status"] == "CRITICAL"
    assert any(
        item["code"] == "SAFETY_VIOLATION"
        for item in snapshot["alerts"]
    )
    assert snapshot["score"] < 75


def test_monitor_warns_on_stale_data(
    tmp_path,
):
    write_report(
        tmp_path,
        finished_at=(
            "2026-07-25T11:00:00+00:00"
        ),
    )

    snapshot = monitor_for(
        tmp_path
    ).snapshot()

    assert snapshot["status"] == "WARNING"
    assert any(
        item["code"] == "DATA_STALE"
        for item in snapshot["alerts"]
    )


def test_monitor_dashboard_is_read_only_html():
    from app.api.routers.paper_performance_monitor import (
        performance_monitor_dashboard,
    )

    response = asyncio.run(
        performance_monitor_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Monitor Paper" in body
    assert "Execução live bloqueada" in body
    assert (
        response.headers[
            "x-predarb-live-execution"
        ]
        == "false"
    )


def test_application_registers_monitor_routes():
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

    required = {
        "/paper/performance/monitor/health",
        "/paper/performance/monitor/alerts",
        "/paper/performance/monitor/score",
        "/paper/performance/monitor/snapshot",
        "/paper/performance/monitor/dashboard",
    }

    assert not (
        required - paths
    )
