from __future__ import annotations

import asyncio

import pytest

from app.paper.final_paper_validation_evidence_incident_runtime import (
    FinalPaperEvidenceIncidentRuntime,
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


class JournalStub:
    def __init__(
        self,
        storage,
        *,
        monitor_status="HEALTHY",
    ):
        self.storage = storage
        self.monitor_status = monitor_status

    def capture(self):
        self.storage.append(
            self.monitor_status
        )

        return {
            "status": "captured",
            "created": [
                "fpe-1"
            ],
            "updated": [],
            "reactivated": [],
            "resolved": [],
            "monitor": {
                "status": self.monitor_status,
                "score": 100,
                "alerts": [],
                **safe_flags(),
            },
            "summary": {
                "active_incidents": 1,
                "active_critical": 0,
                **safe_flags(),
            },
            **safe_flags(),
        }


class FailingJournalStub:
    def capture(self):
        raise RuntimeError(
            "Falha simulada"
        )


def runtime_with(
    storage,
    *,
    enabled=True,
    journal_factory=None,
    monitor_status="HEALTHY",
):
    return FinalPaperEvidenceIncidentRuntime(
        journal_factory=(
            journal_factory
            or (
                lambda: JournalStub(
                    storage,
                    monitor_status=monitor_status,
                )
            )
        ),
        enabled=enabled,
        interval_seconds=0.03,
        minimum_interval_seconds=0.01,
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
    assert status["live_authorization"] is False
    assert (
        status["next_step_authorized"]
        is False
    )


def test_manual_cycle_updates_counters():
    storage = []
    runtime = runtime_with(
        storage
    )

    result = asyncio.run(
        runtime.capture_once()
    )

    assert result["status"] == "SUCCESS"
    assert result["monitor_status"] == "HEALTHY"
    assert result["created_count"] == 1
    assert len(storage) == 1
    assert runtime.created_incidents == 1
    assert runtime.healthy_cycles == 1


def test_monitor_status_counters():
    runtime = runtime_with(
        [],
        monitor_status="CRITICAL",
    )

    result = asyncio.run(
        runtime.capture_once()
    )

    assert result["monitor_status"] == "CRITICAL"
    assert runtime.critical_cycles == 1
    assert runtime.healthy_cycles == 0


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

        return (
            storage,
            stopped,
        )

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

        return (
            first,
            second,
            same_task,
        )

    first, second, same_task = asyncio.run(
        scenario()
    )

    assert first["running"] is True
    assert second["running"] is True
    assert same_task is True


def test_runtime_records_failure():
    runtime = runtime_with(
        [],
        journal_factory=(
            FailingJournalStub
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
    assert (
        status["last_error"]
        == "Falha simulada"
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
    assert reset["created_incidents"] == 0
    assert reset["healthy_cycles"] == 0
    assert reset["last_result"] is None


def test_application_registers_runtime_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_validation_evidence_incident_runtime import (
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
        "/paper/final-validation/evidence/incident-runtime/health",
        "/paper/final-validation/evidence/incident-runtime/status",
        "/paper/final-validation/evidence/incident-runtime/last-cycle",
        "/paper/final-validation/evidence/incident-runtime/cycle",
        "/paper/final-validation/evidence/incident-runtime/start",
        "/paper/final-validation/evidence/incident-runtime/stop",
        "/paper/final-validation/evidence/incident-runtime/reset-statistics",
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
        "/paper/final-validation/evidence/incident-runtime/cycle",
        "/paper/final-validation/evidence/incident-runtime/start",
        "/paper/final-validation/evidence/incident-runtime/stop",
        "/paper/final-validation/evidence/incident-runtime/reset-statistics",
    ):
        assert methods[path] == {"POST"}

    for path in (
        "/paper/final-validation/evidence/incident-runtime/health",
        "/paper/final-validation/evidence/incident-runtime/status",
        "/paper/final-validation/evidence/incident-runtime/last-cycle",
    ):
        assert methods[path] == {"GET"}
