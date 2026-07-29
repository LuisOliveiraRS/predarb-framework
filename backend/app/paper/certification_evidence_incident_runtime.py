from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any

from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)
from app.paper.certification_evidence_monitor import (
    PaperCertificationEvidenceMonitor,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return bool(default)

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }


def _env_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return float(default)

    try:
        return float(value)
    except ValueError:
        return float(default)


class PaperEvidenceIncidentRuntime:
    """Runtime manual para capturar o monitor no journal de incidentes."""

    def __init__(
        self,
        *,
        monitor_factory: Callable[
            [],
            PaperCertificationEvidenceMonitor,
        ] = PaperCertificationEvidenceMonitor,
        journal_factory: Callable[
            [],
            PaperCertificationEvidenceIncidentJournal,
        ] = PaperCertificationEvidenceIncidentJournal,
        enabled: bool | None = None,
        interval_seconds: float | None = None,
        minimum_interval_seconds: float = 30.0,
    ) -> None:
        self.monitor_factory = monitor_factory
        self.journal_factory = journal_factory

        self.enabled = (
            _env_bool(
                "PAPER_EVIDENCE_INCIDENT_RUNTIME_ENABLED",
                True,
            )
            if enabled is None
            else bool(enabled)
        )

        self.minimum_interval_seconds = max(
            0.01,
            float(minimum_interval_seconds),
        )

        configured_interval = (
            _env_float(
                "PAPER_EVIDENCE_INCIDENT_RUNTIME_INTERVAL_SECONDS",
                300.0,
            )
            if interval_seconds is None
            else float(interval_seconds)
        )

        self.interval_seconds = self._normalize_interval(
            configured_interval
        )

        self._task: asyncio.Task[None] | None = None
        self._stop_event: asyncio.Event | None = None
        self._state_lock = asyncio.Lock()
        self._cycle_lock = asyncio.Lock()

        self.started_at: str | None = None
        self.stopped_at: str | None = None
        self.last_cycle_at: str | None = None
        self.last_success_at: str | None = None
        self.last_error_at: str | None = None
        self.last_error: str | None = None
        self.last_result: dict[str, Any] | None = None

        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.created_incidents = 0
        self.updated_incidents = 0
        self.reactivated_incidents = 0
        self.resolved_incidents = 0

    def _normalize_interval(
        self,
        value: float,
    ) -> float:
        return max(
            self.minimum_interval_seconds,
            min(float(value), 86400.0),
        )

    @property
    def running(self) -> bool:
        return (
            self._task is not None
            and not self._task.done()
        )

    @staticmethod
    def _safe_flags() -> dict[str, bool]:
        return {
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }

    def status(self) -> dict[str, Any]:
        payload = {
            "status": (
                "RUNNING"
                if self.running
                else "STOPPED"
            ),
            "enabled": self.enabled,
            "running": self.running,
            "interval_seconds": self.interval_seconds,
            "started_at": self.started_at,
            "stopped_at": self.stopped_at,
            "last_cycle_at": self.last_cycle_at,
            "last_success_at": self.last_success_at,
            "last_error_at": self.last_error_at,
            "last_error": self.last_error,
            "last_result": self.last_result,
            "total_cycles": self.total_cycles,
            "successful_cycles": self.successful_cycles,
            "failed_cycles": self.failed_cycles,
            "created_incidents": self.created_incidents,
            "updated_incidents": self.updated_incidents,
            "reactivated_incidents": self.reactivated_incidents,
            "resolved_incidents": self.resolved_incidents,
            "manual_start_required": True,
            "read_only_monitoring": True,
        }

        payload.update(self._safe_flags())
        return payload

    @staticmethod
    def _validate_safe_payload(
        name: str,
        payload: dict[str, Any],
    ) -> None:
        required_false = (
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if payload.get("read_only") is not True:
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    def _capture_sync(self) -> dict[str, Any]:
        monitor_snapshot = (
            self.monitor_factory().snapshot()
        )

        self._validate_safe_payload(
            "monitor",
            monitor_snapshot,
        )

        result = self.journal_factory().capture(
            monitor_snapshot
        )

        self._validate_safe_payload(
            "journal",
            result,
        )

        return {
            "monitor": monitor_snapshot,
            "journal": result,
        }

    async def capture_once(self) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de incidentes das evidências está desabilitado."
            )

        async with self._cycle_lock:
            started = time.perf_counter()
            captured_at = _utc_now()

            self.total_cycles += 1
            self.last_cycle_at = captured_at

            try:
                payload = await asyncio.to_thread(
                    self._capture_sync
                )

                journal_result = payload["journal"]

                created = len(
                    journal_result.get("created") or []
                )
                updated = len(
                    journal_result.get("updated") or []
                )
                reactivated = len(
                    journal_result.get("reactivated") or []
                )
                resolved = len(
                    journal_result.get("resolved") or []
                )

                self.created_incidents += created
                self.updated_incidents += updated
                self.reactivated_incidents += reactivated
                self.resolved_incidents += resolved

                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    3,
                )

                result = {
                    "status": "SUCCESS",
                    "captured_at": captured_at,
                    "elapsed_ms": elapsed_ms,
                    "monitor_status": payload[
                        "monitor"
                    ].get("status"),
                    "monitor_score": payload[
                        "monitor"
                    ].get("score"),
                    "created": created,
                    "updated": updated,
                    "reactivated": reactivated,
                    "resolved": resolved,
                    "journal_summary": journal_result.get(
                        "summary"
                    ),
                    **self._safe_flags(),
                }

                self.successful_cycles += 1
                self.last_success_at = captured_at
                self.last_error = None
                self.last_result = result

                return result

            except Exception as exc:
                elapsed_ms = round(
                    (
                        time.perf_counter()
                        - started
                    )
                    * 1000,
                    3,
                )

                self.failed_cycles += 1
                self.last_error_at = captured_at
                self.last_error = str(exc)

                result = {
                    "status": "FAILED",
                    "captured_at": captured_at,
                    "elapsed_ms": elapsed_ms,
                    "error": str(exc),
                    **self._safe_flags(),
                }

                self.last_result = result
                raise

    async def _run_loop(
        self,
        *,
        run_immediately: bool,
    ) -> None:
        stop_event = self._stop_event

        if stop_event is None:
            return

        try:
            if run_immediately:
                try:
                    await self.capture_once()
                except Exception:
                    pass

            while not stop_event.is_set():
                try:
                    await asyncio.wait_for(
                        stop_event.wait(),
                        timeout=self.interval_seconds,
                    )
                    break

                except asyncio.TimeoutError:
                    try:
                        await self.capture_once()
                    except Exception:
                        continue

        except asyncio.CancelledError:
            raise

        finally:
            self.stopped_at = _utc_now()

    async def start(
        self,
        *,
        interval_seconds: float | None = None,
        run_immediately: bool = True,
    ) -> dict[str, Any]:
        if not self.enabled:
            raise RuntimeError(
                "O runtime de incidentes das evidências está desabilitado."
            )

        async with self._state_lock:
            if self.running:
                return self.status()

            if interval_seconds is not None:
                self.interval_seconds = (
                    self._normalize_interval(
                        interval_seconds
                    )
                )

            self._stop_event = asyncio.Event()
            self.started_at = _utc_now()
            self.stopped_at = None

            self._task = asyncio.create_task(
                self._run_loop(
                    run_immediately=run_immediately
                ),
                name=(
                    "predarb-paper-evidence-"
                    "incident-runtime"
                ),
            )

            return self.status()

    async def stop(self) -> dict[str, Any]:
        async with self._state_lock:
            task = self._task
            stop_event = self._stop_event

            if task is None or task.done():
                self._task = None
                self._stop_event = None
                self.stopped_at = (
                    self.stopped_at
                    or _utc_now()
                )
                return self.status()

            if stop_event is not None:
                stop_event.set()

        try:
            await asyncio.wait_for(
                task,
                timeout=30.0,
            )

        except asyncio.TimeoutError:
            task.cancel()

            try:
                await task
            except asyncio.CancelledError:
                pass

        finally:
            async with self._state_lock:
                if self._task is task:
                    self._task = None
                    self._stop_event = None

                self.stopped_at = _utc_now()

        return self.status()

    async def reset_statistics(
        self,
    ) -> dict[str, Any]:
        if self.running:
            raise RuntimeError(
                "Pare o runtime antes de resetar as estatísticas."
            )

        self.started_at = None
        self.stopped_at = None
        self.last_cycle_at = None
        self.last_success_at = None
        self.last_error_at = None
        self.last_error = None
        self.last_result = None

        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.created_incidents = 0
        self.updated_incidents = 0
        self.reactivated_incidents = 0
        self.resolved_incidents = 0

        return self.status()


paper_evidence_incident_runtime = (
    PaperEvidenceIncidentRuntime()
)
