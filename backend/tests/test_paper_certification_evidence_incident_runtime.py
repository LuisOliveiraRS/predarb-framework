from __future__ import annotations

import asyncio

import pytest

from app.paper.certification_evidence_incident_runtime import (
    PaperEvidenceIncidentRuntime,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


class MonitorStub:
    def snapshot(self):
        return {
            "status": "WARNING",
            "score": 79,
            "alerts": [],
            "diagnostics": {},
            **safe_flags(),
        }


class JournalStub:
    def __init__(self, storage):
        self.storage = storage

    def capture(self, snapshot):
        self.storage.append(snapshot)

        return {
            "status": "captured",
            "created": [],
            "updated": [],
            "reactivated": [],
            "resolved": [],
            "summary": {
                "active_incidents": 0,
            },
            **safe_flags(),
        }


class FailingJournalStub:
    def capture(self, snapshot):
        raise RuntimeError(
            "Falha simulada"
        )


def runtime_with(
    storage,
    *,
    enabled=True,
    journal_factory=None,
):
    return PaperEvidenceIncidentRuntime(
        monitor_factory=MonitorStub,
        journal_factory=(
            journal_factory
            or (
                lambda: JournalStub(storage)
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
    assert status["manual_start_required"] is True
    assert status["execution_authorized"] is False
    assert status["live_execution"] is False
    assert status["financial_execution"] is False
    assert status["live_authorization"] is False


def test_manual_cycle_captures_monitor():
    storage = []
    runtime = runtime_with(storage)

    result = asyncio.run(
        runtime.capture_once()
    )

    assert result["status"] == "SUCCESS"
    assert result["monitor_status"] == "WARNING"
    assert len(storage) == 1
    assert runtime.total_cycles == 1
    assert runtime.successful_cycles == 1


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
    assert stopped["successful_cycles"] >= 2


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

        same_task = runtime._task is task

        await runtime.stop()

        return first, second, same_task

    first, second, same_task = asyncio.run(
        scenario()
    )

    assert first["running"] is True
    assert second["running"] is True
    assert same_task is True


def test_runtime_records_failure():
    runtime = runtime_with(
        [],
        journal_factory=FailingJournalStub,
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

        return await runtime.reset_statistics()

    reset = asyncio.run(scenario())

    assert reset["total_cycles"] == 0
    assert reset["successful_cycles"] == 0
    assert reset["failed_cycles"] == 0
    assert reset["last_result"] is None


def test_application_registers_runtime_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_evidence_incident_runtime import (
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
        "/paper/certification/evidence/incident-runtime/health",
        "/paper/certification/evidence/incident-runtime/status",
        "/paper/certification/evidence/incident-runtime/last-cycle",
        "/paper/certification/evidence/incident-runtime/cycle",
        "/paper/certification/evidence/incident-runtime/start",
        "/paper/certification/evidence/incident-runtime/stop",
        "/paper/certification/evidence/incident-runtime/reset-statistics",
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
        "/paper/certification/evidence/incident-runtime/cycle",
        "/paper/certification/evidence/incident-runtime/start",
        "/paper/certification/evidence/incident-runtime/stop",
        "/paper/certification/evidence/incident-runtime/reset-statistics",
    ):
        assert methods[path] == {"POST"}

    for path in (
        "/paper/certification/evidence/incident-runtime/health",
        "/paper/certification/evidence/incident-runtime/status",
        "/paper/certification/evidence/incident-runtime/last-cycle",
    ):
        assert methods[path] == {"GET"}
