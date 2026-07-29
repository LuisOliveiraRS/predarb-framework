from __future__ import annotations

import asyncio
import csv
import io
import json

from app.api.routers.paper_performance_dashboard import (
    paper_performance_dashboard,
    paper_performance_export_csv,
    paper_performance_snapshot,
)


def write_report(
    directory,
):
    report_path = (
        directory
        / "phase8_long_session_dashboard.json"
    )

    report_path.write_text(
        json.dumps(
            {
                "label": "dashboard-test",
                "started_at":
                    "2026-07-28T00:00:00+00:00",
                "finished_at":
                    "2026-07-28T00:02:00+00:00",
                "actual_duration_seconds": 120,
                "summary": {
                    "status": "PASS",
                    "samples": 2,
                    "endpoint_errors": 0,
                    "safety_violations": 0,
                },
                "performance": {
                    "cycles_delta": 5,
                    "successful_cycles_delta": 4,
                    "failed_cycles_delta": 1,
                    "no_signal_cycles_delta": 0,
                    "risk_stopped_cycles_delta": 0,
                    "trade_count_delta": 6,
                    "start_equity": 10000,
                    "end_equity": 10002.65,
                    "equity_delta": 2.65,
                    "session_return_rate": 0.000265,
                    "max_drawdown": 0,
                    "max_drawdown_rate": 0,
                },
                "execution_authorized": False,
                "live_execution": False,
            }
        ),
        encoding="utf-8",
    )

    csv_path = report_path.with_suffix(
        ".csv"
    )

    with csv_path.open(
        "w",
        encoding="utf-8-sig",
        newline="",
    ) as file:
        writer = csv.DictWriter(
            file,
            fieldnames=[
                "captured_at",
                "equity",
                "total_cycles",
                "trade_count",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "captured_at":
                    "2026-07-28T00:00:00+00:00",
                "equity": "10000",
                "total_cycles": "0",
                "trade_count": "0",
            }
        )
        writer.writerow(
            {
                "captured_at":
                    "2026-07-28T00:02:00+00:00",
                "equity": "10002.65",
                "total_cycles": "5",
                "trade_count": "6",
            }
        )


def test_dashboard_is_read_only_html():
    response = asyncio.run(
        paper_performance_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert "Desempenho Paper" in body
    assert "Execução live bloqueada" in body
    assert "Painel somente leitura" in body


def test_snapshot_returns_safe_consolidated_data(
    tmp_path,
    monkeypatch,
):
    write_report(tmp_path)

    monkeypatch.setenv(
        "REAL_TEST_REPORTS_DIR",
        str(tmp_path),
    )

    payload = asyncio.run(
        paper_performance_snapshot(
            report_limit=50,
            history_limit=1000,
        )
    )

    assert payload["summary"]["total_reports"] == 1
    assert len(payload["reports"]) == 1
    assert len(payload["history"]) == 2
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["read_only"] is True


def test_export_csv_contains_history(
    tmp_path,
    monkeypatch,
):
    write_report(tmp_path)

    monkeypatch.setenv(
        "REAL_TEST_REPORTS_DIR",
        str(tmp_path),
    )

    response = asyncio.run(
        paper_performance_export_csv(
            history_limit=5000
        )
    )

    body = response.body.decode(
        "utf-8-sig"
    )

    rows = list(
        csv.DictReader(
            io.StringIO(body)
        )
    )

    assert response.status_code == 200
    assert len(rows) == 2
    assert rows[-1]["equity"] == "10002.65"
    assert (
        response.headers[
            "x-predarb-live-execution"
        ]
        == "false"
    )


def test_application_registers_dashboard_routes():
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
        "/paper/performance/dashboard"
        in paths
    )
    assert (
        "/paper/performance/snapshot"
        in paths
    )
    assert (
        "/paper/performance/export.csv"
        in paths
    )


def test_snapshot_is_not_an_execution_endpoint():
    from app.api.routers.paper_performance_dashboard import (
        router,
    )

    method_map = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert method_map[
        "/paper/performance/dashboard"
    ] == {"GET"}

    assert method_map[
        "/paper/performance/snapshot"
    ] == {"GET"}

    assert method_map[
        "/paper/performance/export.csv"
    ] == {"GET"}
