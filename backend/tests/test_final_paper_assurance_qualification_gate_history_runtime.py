from __future__ import annotations

import asyncio

import pytest

from app.paper.final_paper_assurance_qualification_gate_history_runtime import (
    FinalPaperAssuranceQualificationGateHistoryRuntime,
)


def safe_flags(
    *,
    read_only=True,
):
    payload = {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }

    if read_only:
        payload["read_only"] = True

    return payload


class GateStub:
    def __init__(
        self,
        *,
        status="QUALIFIED",
        unsafe=False,
    ):
        self.status = status
        self.unsafe = unsafe

    def evaluate(self):
        payload = {
            "status": self.status,
            "qualified": (
                self.status == "QUALIFIED"
            ),
            "scope": (
                "PAPER_ASSURANCE_QUALIFICATION_ONLY"
            ),
            "qualification_score": (
                100
                if self.status == "QUALIFIED"
                else 75
            ),
            "summary": {
                "assurance_status": "ASSURED",
                "assurance_score": 100,
                "current_streak": 3,
                "active_incidents": 0,
                "active_critical_incidents": 0,
                "total_runtime_failures": 0,
            },
            "criteria": {},
            "checks": [],
            "failures": [],
            **safe_flags(),
        }

        if self.unsafe:
            payload["next_step_authorized"] = True

        return payload


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
        self.storage.append(
            report["status"]
        )

        return {
            "status": "captured",
            "entry": {
                "id": f"entry-{len(self.storage)}",
                "status": report["status"],
                **safe_flags(),
            },
            "summary": {
                "total_entries": len(
                    self.storage
                ),
                **safe_flags(),
            },
            **safe_flags(),
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
    gate=None,
    history_factory=None,
    enabled=True,
):
    return (
        FinalPaperAssuranceQualificationGateHistoryRuntime(
            gate_provider=(
                gate
                or GateStub()
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
    )


def test_runtime_starts_stopped_and_safe():
    status = runtime_with(
        []
    ).status()

    assert status["status"] == "STOPPED"
    assert status["running"] is False
    assert status["manual_start_required"] is True
    assert (
        status["paper_execution_authorized"]
        is False
    )
    assert (
        status["next_step_authorized"]
        is False
    )


def test_manual_cycle_captures_gate():
    storage = []
    runtime = runtime_with(
        storage
    )

    result = asyncio.run(
        runtime.capture_once()
    )

    assert result["status"] == "SUCCESS"
    assert (
        result["gate_status"]
        == "QUALIFIED"
    )
    assert result["history_entries"] == 1
    assert storage == ["QUALIFIED"]
    assert runtime.qualified_cycles == 1


def test_status_counters_are_updated():
    runtime = runtime_with(
        [],
        gate=GateStub(
            status="PENDING"
        ),
    )

    result = asyncio.run(
        runtime.capture_once()
    )

    assert (
        result["gate_status"]
        == "PENDING"
    )
    assert runtime.pending_cycles == 1
    assert runtime.qualified_cycles == 0


def test_runtime_processes_periodic_cycles():
    async def scenario():
        storage = []
        runtime = runtime_with(
            storage
        )

        await runtime.start(
            interval_seconds=0.02,
            run_immediately=True,
        )

        await asyncio.sleep(
            0.08
        )

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
        runtime = runtime_with(
            []
        )

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

        return first, second, same_task

    first, second, same_task = asyncio.run(
        scenario()
    )

    assert first["running"] is True
    assert second["running"] is True
    assert same_task is True


def test_runtime_records_capture_failure():
    runtime = runtime_with(
        [],
        history_factory=FailingHistoryStub,
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
    assert (
        status["last_error"]
        == "Falha simulada"
    )


def test_runtime_rejects_unsafe_gate():
    runtime = runtime_with(
        [],
        gate=GateStub(
            unsafe=True
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="next_step_authorized",
    ):
        asyncio.run(
            runtime.capture_once()
        )


def test_reset_statistics_clears_counters():
    async def scenario():
        runtime = runtime_with(
            []
        )

        await runtime.capture_once()

        return await runtime.reset_statistics()

    reset = asyncio.run(
        scenario()
    )

    assert reset["total_cycles"] == 0
    assert reset["successful_cycles"] == 0
    assert reset["qualified_cycles"] == 0
    assert reset["last_result"] is None


def test_application_registers_runtime_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_assurance_qualification_gate_history_runtime import (
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
        "/paper/final-assurance/qualification-gate/history-runtime/health",
        "/paper/final-assurance/qualification-gate/history-runtime/status",
        "/paper/final-assurance/qualification-gate/history-runtime/last-cycle",
        "/paper/final-assurance/qualification-gate/history-runtime/cycle",
        "/paper/final-assurance/qualification-gate/history-runtime/start",
        "/paper/final-assurance/qualification-gate/history-runtime/stop",
        "/paper/final-assurance/qualification-gate/history-runtime/reset-statistics",
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
        "/paper/final-assurance/qualification-gate/history-runtime/cycle",
        "/paper/final-assurance/qualification-gate/history-runtime/start",
        "/paper/final-assurance/qualification-gate/history-runtime/stop",
        "/paper/final-assurance/qualification-gate/history-runtime/reset-statistics",
    ):
        assert methods[path] == {"POST"}

    for path in (
        "/paper/final-assurance/qualification-gate/history-runtime/health",
        "/paper/final-assurance/qualification-gate/history-runtime/status",
        "/paper/final-assurance/qualification-gate/history-runtime/last-cycle",
    ):
        assert methods[path] == {"GET"}
