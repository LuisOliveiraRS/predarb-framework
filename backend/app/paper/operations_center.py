from __future__ import annotations

from collections.abc import Callable
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.performance import (
    PaperPerformanceService,
)
from app.paper.performance_incident_runtime import (
    PaperIncidentRuntime,
    paper_incident_runtime,
)
from app.paper.performance_incidents import (
    PaperIncidentJournal,
)
from app.paper.performance_monitor import (
    PaperPerformanceMonitor,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


class PaperOperationsCenter:
    """Visão consolidada e somente leitura da operação Paper."""

    def __init__(
        self,
        *,
        performance_factory: Callable[
            [],
            PaperPerformanceService,
        ] = PaperPerformanceService,
        monitor_factory: Callable[
            [],
            PaperPerformanceMonitor,
        ] = PaperPerformanceMonitor,
        journal_factory: Callable[
            [],
            PaperIncidentJournal,
        ] = PaperIncidentJournal,
        runtime: PaperIncidentRuntime = (
            paper_incident_runtime
        ),
    ) -> None:
        self.performance_factory = performance_factory
        self.monitor_factory = monitor_factory
        self.journal_factory = journal_factory
        self.runtime = runtime

    @staticmethod
    def _validate_safe_component(
        name: str,
        payload: Mapping[str, Any],
    ) -> None:
        if payload.get(
            "execution_authorized"
        ) is not False:
            raise RuntimeError(
                f"{name}: execução não está "
                "explicitamente bloqueada."
            )

        if payload.get(
            "live_execution"
        ) is not False:
            raise RuntimeError(
                f"{name}: execução live não está "
                "explicitamente bloqueada."
            )

        if (
            "financial_execution" in payload
            and payload.get(
                "financial_execution"
            )
            is not False
        ):
            raise RuntimeError(
                f"{name}: execução financeira "
                "não está bloqueada."
            )

    @staticmethod
    def _overall_status(
        *,
        performance: Mapping[str, Any],
        monitor: Mapping[str, Any],
        incidents: Mapping[str, Any],
        runtime: Mapping[str, Any],
    ) -> str:
        monitor_status = str(
            monitor.get("status") or "UNKNOWN"
        ).upper()

        safety_violations = _integer(
            performance.get(
                "safety_violations"
            )
        )

        endpoint_errors = _integer(
            performance.get(
                "endpoint_errors"
            )
        )

        active_critical = _integer(
            incidents.get(
                "active_critical"
            )
        )

        active_warning = _integer(
            incidents.get(
                "active_warning"
            )
        )

        failed_runtime_cycles = _integer(
            runtime.get(
                "failed_cycles"
            )
        )

        if (
            monitor_status == "CRITICAL"
            or safety_violations > 0
            or active_critical > 0
        ):
            return "CRITICAL"

        if monitor_status == "NO_DATA":
            return "NO_DATA"

        if (
            monitor_status == "WARNING"
            or endpoint_errors > 0
            or active_warning > 0
            or failed_runtime_cycles > 0
        ):
            return "WARNING"

        if monitor_status == "HEALTHY":
            return "HEALTHY"

        return "UNKNOWN"

    @staticmethod
    def _links() -> dict[str, str]:
        return {
            "performance_dashboard": (
                "/paper/performance/dashboard"
            ),
            "monitor_dashboard": (
                "/paper/performance/monitor/dashboard"
            ),
            "incidents_dashboard": (
                "/paper/performance/incidents/dashboard"
            ),
            "runtime_dashboard": (
                "/paper/performance/incidents/"
                "runtime/dashboard"
            ),
        }

    def snapshot(
        self,
    ) -> dict[str, Any]:
        performance = (
            self.performance_factory().summary()
        )

        monitor = (
            self.monitor_factory().snapshot()
        )

        incidents = (
            self.journal_factory().summary()
        )

        runtime = self.runtime.status()

        self._validate_safe_component(
            "performance",
            performance,
        )

        self._validate_safe_component(
            "monitor",
            monitor,
        )

        self._validate_safe_component(
            "incidents",
            incidents,
        )

        self._validate_safe_component(
            "runtime",
            runtime,
        )

        overall_status = self._overall_status(
            performance=performance,
            monitor=monitor,
            incidents=incidents,
            runtime=runtime,
        )

        return {
            "status": overall_status,
            "generated_at": _utc_now(),
            "performance": performance,
            "monitor": monitor,
            "incidents": incidents,
            "runtime": runtime,
            "links": self._links(),
            "diagnostics": {
                "monitor_score": _integer(
                    monitor.get("score")
                ),
                "reports": _integer(
                    performance.get(
                        "total_reports"
                    )
                ),
                "cycles": _integer(
                    performance.get(
                        "total_cycles"
                    )
                ),
                "trades": _integer(
                    performance.get(
                        "total_trades"
                    )
                ),
                "active_incidents": _integer(
                    incidents.get(
                        "active_incidents"
                    )
                ),
                "runtime_cycles": _integer(
                    runtime.get(
                        "total_cycles"
                    )
                ),
                "runtime_failures": _integer(
                    runtime.get(
                        "failed_cycles"
                    )
                ),
            },
            "manual_start_required": True,
            "read_only": True,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }


paper_operations_center = PaperOperationsCenter()
