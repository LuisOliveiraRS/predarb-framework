from __future__ import annotations

import asyncio

import pytest

from app.paper.readiness_runtime import (
    PaperReadinessRuntime,
)


def safe_report(
    status="READY",
    score=90,
):
    return {
        "status": status,
        "ready": status == "READY",
        "generated_at":
            "2026-07-28T12:00:00+00:00",
        "readiness_score": score,
        "summary": {
            "passed_checks": 11,
            "blockers": 0,
            "warnings": 0,
            "insufficient_data": 0,
        },
        "thresholds": {},
        "checks": [],
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


class GateStub:
    def __init__(
        self,
        report=None,
    ):
        self.report = (
            report
            or safe_report()
        )

    def evaluate(self):
        return self.report


class HistoryStub:
    def __init__(
        self,
        storage,
    ):
        self.storage = storage

    def capture(
        self,
        report,
    ):
        self.storage.append(report)

        return {
            "status": "captured",
            "entry": {
                "id": (
                    f"entry-{len(self.storage)}"
                ),
                "status": report["status"],
            },
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }


class FailingHistoryStub:
    def capture(
        self,
        report,
    ):
        raise RuntimeError(
            "Falha simulada"
        )


def runtime_with(
    storage,
    *,
    report=None,
    history_factory=None,
    enabled=True,
):
    return PaperReadinessRuntime(
        gate_factory=lambda: GateStub(
            report
        ),
        history_factory=(
            history_factory
            or (
                lambda: HistoryStub(
                    storage
                )
            )
        ),
        enabled=enabled,
        interval_seconds=0.03,
        minimum_interval_seconds=0.01,
    )


def test_runtime_starts_stopped_and_safe():
    runtime = runtime_with([])

    status = runtime.status()

    assert status["status"] == "STOPPED"
    assert status["running"] is False
    assert (
        status["manual_start_required"]
        is True
    )
    assert (
        status["execution_authorized"]
        is False
    )
    assert status["live_execution"] is False
    assert (
        status["financial_execution"]
        is False
    )


def test_capture_once_persists_readiness():
    storage = []
    runtime = runtime_with(storage)

    result = asyncio.run(
        runtime.capture_once()
    )

    assert result["status"] == "SUCCESS"
    assert result[
        "readiness_status"
    ] == "READY"
    assert len(storage) == 1
    assert runtime.total_cycles == 1
    assert runtime.successful_cycles == 1
    assert runtime.ready_cycles == 1


def test_capture_counts_insufficient_data():
    storage = []
    runtime = runtime_with(
        storage,
        report=safe_report(
            status="INSUFFICIENT_DATA",
            score=60,
        ),
    )

    asyncio.run(
        runtime.capture_once()
    )

    assert (
        runtime.insufficient_data_cycles
        == 1
    )
    assert runtime.ready_cycles == 0


def test_runtime_processes_periodic_cycles():
    async def scenario():
        storage = []
        runtime = runtime_with(storage)

        await runtime.start(
            interval_seconds=0.02,
            run_immediately=True,
        )

        await asyncio.sleep(0.08)
        stopped = await runtime.stop()

        return storage, stopped

    storage, stopped = asyncio.run(
        scenario()
    )

    assert len(storage) >= 2
    assert stopped["running"] is False
    assert (
        stopped["successful_cycles"]
        >= 2
    )


def test_start_is_idempotent():
    async def scenario():
        runtime = runtime_with([])

        first = await runtime.start(
            run_immediately=False
        )

        task = runtime._task

        second = await runtime.start(
            run_immediately=False
        )

        same_task = (
            runtime._task is task
        )

        await runtime.stop()

        return (
            first,
            second,
            same_task,
        )

    first, second, same_task = (
        asyncio.run(scenario())
    )

    assert first["running"] is True
    assert second["running"] is True
    assert same_task is True


def test_runtime_records_failure():
    runtime = runtime_with(
        [],
        history_factory=(
            FailingHistoryStub
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="Falha simulada",
    ):
        asyncio.run(
            runtime.capture_once()
        )

    status = runtime.status()

    assert status["total_cycles"] == 1
    assert status["failed_cycles"] == 1
    assert status["last_error"] == (
        "Falha simulada"
    )
    assert status["live_execution"] is False


def test_disabled_runtime_rejects_capture():
    runtime = runtime_with(
        [],
        enabled=False,
    )

    with pytest.raises(
        RuntimeError,
        match="desabilitado",
    ):
        asyncio.run(
            runtime.capture_once()
        )


def test_reset_statistics_clears_counters():
    async def scenario():
        runtime = runtime_with([])

        await runtime.capture_once()

        return await (
            runtime.reset_statistics()
        )

    reset = asyncio.run(scenario())

    assert reset["total_cycles"] == 0
    assert (
        reset["successful_cycles"]
        == 0
    )
    assert reset["failed_cycles"] == 0
    assert reset["ready_cycles"] == 0
    assert reset["last_result"] is None


def test_application_registers_runtime_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_readiness_runtime import (
        router,
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
        "/paper/readiness/runtime/health",
        "/paper/readiness/runtime/status",
        "/paper/readiness/runtime/last-cycle",
        "/paper/readiness/runtime/cycle",
        "/paper/readiness/runtime/start",
        "/paper/readiness/runtime/stop",
        "/paper/readiness/runtime/reset-statistics",
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

    for path in (
        "/paper/readiness/runtime/cycle",
        "/paper/readiness/runtime/start",
        "/paper/readiness/runtime/stop",
        "/paper/readiness/runtime/reset-statistics",
    ):
        assert methods[path] == {"POST"}

    for path in (
        "/paper/readiness/runtime/health",
        "/paper/readiness/runtime/status",
        "/paper/readiness/runtime/last-cycle",
    ):
        assert methods[path] == {"GET"}
