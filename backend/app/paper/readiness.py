from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.operations_center import (
    PaperOperationsCenter,
    paper_operations_center,
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


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None or isinstance(value, bool):
        return float(default)

    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return int(default)

    try:
        return int(value)
    except ValueError:
        return int(default)


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


@dataclass(frozen=True)
class ReadinessThresholds:
    min_reports: int
    min_cycles: int
    min_trades: int
    min_monitor_score: int
    max_active_warning_incidents: int
    max_runtime_failures: int

    @classmethod
    def from_env(
        cls,
    ) -> "ReadinessThresholds":
        return cls(
            min_reports=max(
                1,
                _env_int(
                    "PAPER_READINESS_MIN_REPORTS",
                    2,
                ),
            ),
            min_cycles=max(
                1,
                _env_int(
                    "PAPER_READINESS_MIN_CYCLES",
                    20,
                ),
            ),
            min_trades=max(
                0,
                _env_int(
                    "PAPER_READINESS_MIN_TRADES",
                    10,
                ),
            ),
            min_monitor_score=max(
                0,
                min(
                    100,
                    _env_int(
                        "PAPER_READINESS_MIN_MONITOR_SCORE",
                        75,
                    ),
                ),
            ),
            max_active_warning_incidents=max(
                0,
                _env_int(
                    "PAPER_READINESS_MAX_ACTIVE_WARNING_INCIDENTS",
                    5,
                ),
            ),
            max_runtime_failures=max(
                0,
                _env_int(
                    "PAPER_READINESS_MAX_RUNTIME_FAILURES",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class ReadinessCheck:
    code: str
    category: str
    status: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class PaperReadinessGate:
    """Gate somente leitura para qualificação da operação Paper."""

    def __init__(
        self,
        *,
        operations_center: PaperOperationsCenter = (
            paper_operations_center
        ),
        thresholds: ReadinessThresholds | None = None,
    ) -> None:
        self.operations_center = operations_center
        self.thresholds = (
            thresholds
            if thresholds is not None
            else ReadinessThresholds.from_env()
        )

    @staticmethod
    def _validate_safe_snapshot(
        snapshot: Mapping[str, Any],
    ) -> None:
        if snapshot.get(
            "execution_authorized"
        ) is not False:
            raise RuntimeError(
                "O Centro de Operações não bloqueou "
                "explicitamente a execução."
            )

        if snapshot.get(
            "live_execution"
        ) is not False:
            raise RuntimeError(
                "O Centro de Operações não bloqueou "
                "explicitamente a execução live."
            )

        if snapshot.get(
            "financial_execution"
        ) is not False:
            raise RuntimeError(
                "O Centro de Operações não bloqueou "
                "explicitamente a execução financeira."
            )

        if snapshot.get("read_only") is not True:
            raise RuntimeError(
                "O Centro de Operações não está "
                "marcado como somente leitura."
            )

    @staticmethod
    def _check(
        *,
        code: str,
        category: str,
        passed: bool,
        title: str,
        message_pass: str,
        message_fail: str,
        current_value: Any = None,
        expected_value: Any = None,
        fail_status: str = "BLOCKER",
    ) -> ReadinessCheck:
        return ReadinessCheck(
            code=code,
            category=category,
            status=(
                "PASS"
                if passed
                else fail_status
            ),
            title=title,
            message=(
                message_pass
                if passed
                else message_fail
            ),
            current_value=current_value,
            expected_value=expected_value,
        )

    def evaluate(
        self,
    ) -> dict[str, Any]:
        operations = (
            self.operations_center.snapshot()
        )

        self._validate_safe_snapshot(
            operations
        )

        performance = (
            operations.get("performance")
            or {}
        )

        monitor = (
            operations.get("monitor")
            or {}
        )

        incidents = (
            operations.get("incidents")
            or {}
        )

        runtime = (
            operations.get("runtime")
            or {}
        )

        reports = _integer(
            performance.get("total_reports")
        )

        cycles = _integer(
            performance.get("total_cycles")
        )

        trades = _integer(
            performance.get("total_trades")
        )

        endpoint_errors = _integer(
            performance.get("endpoint_errors")
        )

        safety_violations = _integer(
            performance.get(
                "safety_violations"
            )
        )

        monitor_status = str(
            monitor.get("status") or "UNKNOWN"
        ).upper()

        monitor_score = _integer(
            monitor.get("score")
        )

        active_critical = _integer(
            incidents.get("active_critical")
        )

        active_warning = _integer(
            incidents.get("active_warning")
        )

        runtime_failures = _integer(
            runtime.get("failed_cycles")
        )

        checks = [
            self._check(
                code="REPORTS_SUFFICIENT",
                category="DATA",
                passed=(
                    reports
                    >= self.thresholds.min_reports
                ),
                title="Quantidade de relatórios",
                message_pass=(
                    "Há relatórios suficientes para "
                    "avaliar a operação."
                ),
                message_fail=(
                    "Ainda não há relatórios suficientes "
                    "para uma avaliação confiável."
                ),
                current_value=reports,
                expected_value=(
                    self.thresholds.min_reports
                ),
                fail_status="INSUFFICIENT_DATA",
            ),
            self._check(
                code="CYCLES_SUFFICIENT",
                category="DATA",
                passed=(
                    cycles
                    >= self.thresholds.min_cycles
                ),
                title="Quantidade de ciclos",
                message_pass=(
                    "A amostra de ciclos atende ao "
                    "mínimo definido."
                ),
                message_fail=(
                    "A amostra de ciclos ainda está "
                    "abaixo do mínimo."
                ),
                current_value=cycles,
                expected_value=(
                    self.thresholds.min_cycles
                ),
                fail_status="INSUFFICIENT_DATA",
            ),
            self._check(
                code="TRADES_SUFFICIENT",
                category="DATA",
                passed=(
                    trades
                    >= self.thresholds.min_trades
                ),
                title="Quantidade de trades Paper",
                message_pass=(
                    "A quantidade de trades atende ao "
                    "mínimo definido."
                ),
                message_fail=(
                    "A quantidade de trades ainda é "
                    "insuficiente."
                ),
                current_value=trades,
                expected_value=(
                    self.thresholds.min_trades
                ),
                fail_status="INSUFFICIENT_DATA",
            ),
            self._check(
                code="NO_SAFETY_VIOLATIONS",
                category="SAFETY",
                passed=(safety_violations == 0),
                title="Violações de segurança",
                message_pass=(
                    "Nenhuma violação de segurança foi "
                    "registrada."
                ),
                message_fail=(
                    "Há violações de segurança registradas."
                ),
                current_value=safety_violations,
                expected_value=0,
            ),
            self._check(
                code="NO_ENDPOINT_ERRORS",
                category="RELIABILITY",
                passed=(endpoint_errors == 0),
                title="Erros de endpoint",
                message_pass=(
                    "Nenhum erro de endpoint foi "
                    "registrado."
                ),
                message_fail=(
                    "Há erros de endpoint registrados."
                ),
                current_value=endpoint_errors,
                expected_value=0,
            ),
            self._check(
                code="MONITOR_STATUS_ACCEPTABLE",
                category="MONITOR",
                passed=(
                    monitor_status
                    not in {
                        "CRITICAL",
                        "NO_DATA",
                        "UNKNOWN",
                    }
                ),
                title="Estado do monitor",
                message_pass=(
                    "O estado do monitor é compatível "
                    "com a continuidade dos testes Paper."
                ),
                message_fail=(
                    "O estado do monitor impede a "
                    "qualificação da operação."
                ),
                current_value=monitor_status,
                expected_value=(
                    "HEALTHY ou WARNING"
                ),
            ),
            self._check(
                code="MONITOR_SCORE_SUFFICIENT",
                category="MONITOR",
                passed=(
                    monitor_score
                    >= self.thresholds.min_monitor_score
                ),
                title="Score do monitor",
                message_pass=(
                    "O score do monitor atende ao "
                    "mínimo definido."
                ),
                message_fail=(
                    "O score do monitor está abaixo "
                    "do mínimo."
                ),
                current_value=monitor_score,
                expected_value=(
                    self.thresholds.min_monitor_score
                ),
            ),
            self._check(
                code="NO_ACTIVE_CRITICAL_INCIDENTS",
                category="INCIDENTS",
                passed=(active_critical == 0),
                title="Incidentes críticos ativos",
                message_pass=(
                    "Não há incidentes críticos ativos."
                ),
                message_fail=(
                    "Há incidentes críticos ativos."
                ),
                current_value=active_critical,
                expected_value=0,
            ),
            self._check(
                code="WARNING_INCIDENTS_WITHIN_LIMIT",
                category="INCIDENTS",
                passed=(
                    active_warning
                    <= self.thresholds
                    .max_active_warning_incidents
                ),
                title="Incidentes warning ativos",
                message_pass=(
                    "A quantidade de warnings está "
                    "dentro do limite."
                ),
                message_fail=(
                    "A quantidade de warnings ativos "
                    "superou o limite."
                ),
                current_value=active_warning,
                expected_value=(
                    self.thresholds
                    .max_active_warning_incidents
                ),
                fail_status="WARNING",
            ),
            self._check(
                code="RUNTIME_FAILURES_WITHIN_LIMIT",
                category="RUNTIME",
                passed=(
                    runtime_failures
                    <= self.thresholds.max_runtime_failures
                ),
                title="Falhas do runtime",
                message_pass=(
                    "As falhas do runtime estão dentro "
                    "do limite."
                ),
                message_fail=(
                    "As falhas do runtime superaram "
                    "o limite."
                ),
                current_value=runtime_failures,
                expected_value=(
                    self.thresholds.max_runtime_failures
                ),
            ),
            self._check(
                code="FINANCIAL_EXECUTION_BLOCKED",
                category="SAFETY",
                passed=(
                    operations.get(
                        "financial_execution"
                    )
                    is False
                ),
                title="Execução financeira",
                message_pass=(
                    "A execução financeira permanece "
                    "bloqueada."
                ),
                message_fail=(
                    "A execução financeira não está "
                    "bloqueada."
                ),
                current_value=operations.get(
                    "financial_execution"
                ),
                expected_value=False,
            ),
        ]

        blockers = [
            check
            for check in checks
            if check.status == "BLOCKER"
        ]

        insufficient = [
            check
            for check in checks
            if check.status == "INSUFFICIENT_DATA"
        ]

        warnings = [
            check
            for check in checks
            if check.status == "WARNING"
        ]

        passed = [
            check
            for check in checks
            if check.status == "PASS"
        ]

        if blockers:
            status = "NOT_READY"

        elif insufficient:
            status = "INSUFFICIENT_DATA"

        else:
            status = "READY"

        total_checks = len(checks)

        readiness_score = round(
            (
                len(passed)
                / total_checks
                * 100
            )
            if total_checks
            else 0.0,
            2,
        )

        return {
            "status": status,
            "ready": status == "READY",
            "generated_at": _utc_now(),
            "readiness_score": readiness_score,
            "thresholds": asdict(
                self.thresholds
            ),
            "summary": {
                "total_checks": total_checks,
                "passed_checks": len(passed),
                "blockers": len(blockers),
                "warnings": len(warnings),
                "insufficient_data": len(
                    insufficient
                ),
            },
            "checks": [
                check.to_dict()
                for check in checks
            ],
            "blockers": [
                check.to_dict()
                for check in blockers
            ],
            "warnings": [
                check.to_dict()
                for check in warnings
            ],
            "insufficient_data": [
                check.to_dict()
                for check in insufficient
            ],
            "operations_status": operations.get(
                "status"
            ),
            "manual_start_required": True,
            "read_only": True,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }


paper_readiness_gate = PaperReadinessGate()
