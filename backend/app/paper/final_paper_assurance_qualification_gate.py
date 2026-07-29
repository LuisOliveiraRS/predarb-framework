from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from app.paper.final_paper_assurance_history_runtime import (
    final_paper_assurance_history_runtime,
)
from app.paper.final_paper_operational_assurance import (
    final_paper_operational_assurance,
)
from app.paper.final_paper_operational_assurance_history import (
    FinalPaperOperationalAssuranceHistory,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None:
        return float(default)
    try:
        return float(value)
    except ValueError:
        return float(default)


def _env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None:
        return int(default)
    try:
        return int(value)
    except ValueError:
        return int(default)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return float(default)
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


@dataclass(frozen=True)
class FinalPaperAssuranceGateCriteria:
    min_history_entries: int
    min_current_assured_streak: int
    min_current_score: float
    min_average_score: float
    max_runtime_failures: int

    @classmethod
    def from_env(cls) -> "FinalPaperAssuranceGateCriteria":
        return cls(
            min_history_entries=max(
                1,
                _env_int(
                    "PAPER_FINAL_ASSURANCE_GATE_MIN_HISTORY_ENTRIES",
                    3,
                ),
            ),
            min_current_assured_streak=max(
                1,
                _env_int(
                    "PAPER_FINAL_ASSURANCE_GATE_MIN_ASSURED_STREAK",
                    3,
                ),
            ),
            min_current_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_ASSURANCE_GATE_MIN_CURRENT_SCORE",
                        90.0,
                    ),
                ),
            ),
            min_average_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_ASSURANCE_GATE_MIN_AVERAGE_SCORE",
                        90.0,
                    ),
                ),
            ),
            max_runtime_failures=max(
                0,
                _env_int(
                    "PAPER_FINAL_ASSURANCE_GATE_MAX_RUNTIME_FAILURES",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class FinalPaperAssuranceGateCheck:
    code: str
    status: str
    severity: str
    title: str
    message: str
    current_value: Any
    expected_value: Any
    category: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalPaperAssuranceQualificationGate:
    """Gate somente leitura para qualificar a estabilidade final do Paper."""

    def __init__(
        self,
        *,
        assurance_provider: Any = final_paper_operational_assurance,
        history_factory: Callable[
            [], FinalPaperOperationalAssuranceHistory
        ] = FinalPaperOperationalAssuranceHistory,
        history_runtime: Any = final_paper_assurance_history_runtime,
        criteria: FinalPaperAssuranceGateCriteria | None = None,
    ) -> None:
        self.assurance_provider = assurance_provider
        self.history_factory = history_factory
        self.history_runtime = history_runtime
        self.criteria = (
            criteria
            if criteria is not None
            else FinalPaperAssuranceGateCriteria.from_env()
        )

    @staticmethod
    def _safe_flags() -> dict[str, bool]:
        return {
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
            "read_only": True,
        }

    @classmethod
    def _validate_safe_payload(
        cls,
        name: str,
        payload: Mapping[str, Any],
        *,
        require_read_only: bool = True,
    ) -> None:
        for field in (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
            "next_step_authorized",
        ):
            if payload.get(field) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )
        if require_read_only and payload.get("read_only") is not True:
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    @staticmethod
    def _check(
        *,
        code: str,
        passed: bool,
        severity: str,
        title: str,
        pass_message: str,
        fail_message: str,
        current_value: Any,
        expected_value: Any,
        category: str,
    ) -> FinalPaperAssuranceGateCheck:
        return FinalPaperAssuranceGateCheck(
            code=code,
            status="PASS" if passed else "FAIL",
            severity="none" if passed else severity,
            title=title,
            message=pass_message if passed else fail_message,
            current_value=current_value,
            expected_value=expected_value,
            category=category,
        )

    def evaluate(self) -> dict[str, Any]:
        assurance = self.assurance_provider.evaluate()
        history = self.history_factory().summary()
        runtime = self.history_runtime.status()

        if not isinstance(assurance, Mapping):
            raise RuntimeError("A garantia final não retornou um objeto.")
        if not isinstance(history, Mapping):
            raise RuntimeError("O histórico da garantia final não retornou um objeto.")
        if not isinstance(runtime, Mapping):
            raise RuntimeError("O runtime do histórico da garantia final não retornou um objeto.")

        self._validate_safe_payload("final_assurance", assurance)
        self._validate_safe_payload("final_assurance_history", history)
        self._validate_safe_payload(
            "final_assurance_history_runtime",
            runtime,
            require_read_only=False,
        )

        if assurance.get("scope") != "PAPER_ASSURANCE_ONLY":
            raise RuntimeError("Escopo da garantia final inválido.")

        assurance_status = str(assurance.get("status") or "NO_DATA").upper()
        assurance_score = _number(assurance.get("assurance_score"))
        assurance_summary = assurance.get("summary") or {}

        history_entries = _integer(history.get("total_entries"))
        latest_history_status = str(
            history.get("latest_status") or "NO_DATA"
        ).upper()
        latest_history_score = _number(history.get("latest_score"))
        average_history_score = _number(history.get("average_score"))
        current_streak_status = str(
            history.get("current_streak_status") or "NO_DATA"
        ).upper()
        current_streak = _integer(history.get("current_streak"))

        active_incidents = _integer(
            assurance_summary.get("active_incidents")
        )
        active_critical_incidents = _integer(
            assurance_summary.get("active_critical_incidents")
        )
        integrity_status = str(
            assurance_summary.get("integrity_status") or "EMPTY"
        ).upper()
        monitor_status = str(
            assurance_summary.get("monitor_status") or "NO_DATA"
        ).upper()
        component_errors = _integer(
            assurance_summary.get("component_errors")
        )
        assurance_runtime_failures = _integer(
            assurance_summary.get("total_runtime_failures")
        )
        history_runtime_failures = _integer(runtime.get("failed_cycles"))
        total_runtime_failures = (
            assurance_runtime_failures + history_runtime_failures
        )

        c = self.criteria
        checks = [
            self._check(
                code="CURRENT_ASSURANCE_STATUS",
                passed=assurance_status == "ASSURED",
                severity="critical" if assurance_status == "BLOCKED" else "warning",
                title="Garantia operacional atual",
                pass_message="A Garantia Operacional Final está ASSURED.",
                fail_message="A Garantia Operacional Final ainda não está ASSURED.",
                current_value=assurance_status,
                expected_value="ASSURED",
                category="assurance",
            ),
            self._check(
                code="CURRENT_ASSURANCE_SCORE",
                passed=assurance_score >= c.min_current_score,
                severity="warning",
                title="Score atual da garantia",
                pass_message="O score atual atende ao mínimo configurado.",
                fail_message="O score atual está abaixo do mínimo configurado.",
                current_value=assurance_score,
                expected_value=f">= {c.min_current_score}",
                category="score",
            ),
            self._check(
                code="HISTORY_VOLUME",
                passed=history_entries >= c.min_history_entries,
                severity="warning",
                title="Volume do histórico",
                pass_message="O histórico possui avaliações suficientes.",
                fail_message="O histórico ainda não possui avaliações suficientes.",
                current_value=history_entries,
                expected_value=f">= {c.min_history_entries}",
                category="history",
            ),
            self._check(
                code="LATEST_HISTORY_STATUS",
                passed=latest_history_status == "ASSURED",
                severity="critical" if latest_history_status == "BLOCKED" else "warning",
                title="Último estado persistido",
                pass_message="A última avaliação persistida está ASSURED.",
                fail_message="A última avaliação persistida ainda não está ASSURED.",
                current_value=latest_history_status,
                expected_value="ASSURED",
                category="history",
            ),
            self._check(
                code="LATEST_HISTORY_SCORE",
                passed=latest_history_score >= c.min_current_score,
                severity="warning",
                title="Último score persistido",
                pass_message="O último score persistido atende ao mínimo.",
                fail_message="O último score persistido está abaixo do mínimo.",
                current_value=latest_history_score,
                expected_value=f">= {c.min_current_score}",
                category="history",
            ),
            self._check(
                code="AVERAGE_HISTORY_SCORE",
                passed=average_history_score >= c.min_average_score,
                severity="warning",
                title="Score médio do histórico",
                pass_message="O score médio atende ao mínimo configurado.",
                fail_message="O score médio ainda está abaixo do mínimo.",
                current_value=average_history_score,
                expected_value=f">= {c.min_average_score}",
                category="history",
            ),
            self._check(
                code="CURRENT_ASSURED_STREAK",
                passed=(
                    current_streak_status == "ASSURED"
                    and current_streak >= c.min_current_assured_streak
                ),
                severity="warning",
                title="Sequência atual ASSURED",
                pass_message="A sequência atual ASSURED atende ao mínimo.",
                fail_message="A sequência atual ASSURED ainda é insuficiente.",
                current_value={"status": current_streak_status, "streak": current_streak},
                expected_value={
                    "status": "ASSURED",
                    "streak": f">= {c.min_current_assured_streak}",
                },
                category="stability",
            ),
            self._check(
                code="EVIDENCE_INTEGRITY",
                passed=integrity_status == "VALID",
                severity="critical",
                title="Integridade das evidências",
                pass_message="A integridade probatória está VALID.",
                fail_message="A integridade probatória não está VALID.",
                current_value=integrity_status,
                expected_value="VALID",
                category="evidence",
            ),
            self._check(
                code="EVIDENCE_MONITOR",
                passed=monitor_status == "HEALTHY",
                severity="critical" if monitor_status == "CRITICAL" else "warning",
                title="Monitor das evidências",
                pass_message="O monitor das evidências está HEALTHY.",
                fail_message="O monitor das evidências ainda não está HEALTHY.",
                current_value=monitor_status,
                expected_value="HEALTHY",
                category="monitoring",
            ),
            self._check(
                code="ACTIVE_INCIDENTS",
                passed=active_incidents == 0,
                severity="warning",
                title="Incidentes ativos",
                pass_message="Não existem incidentes ativos.",
                fail_message="Existem incidentes ativos.",
                current_value=active_incidents,
                expected_value=0,
                category="incidents",
            ),
            self._check(
                code="ACTIVE_CRITICAL_INCIDENTS",
                passed=active_critical_incidents == 0,
                severity="critical",
                title="Incidentes críticos ativos",
                pass_message="Não existem incidentes críticos ativos.",
                fail_message="Existem incidentes críticos ativos.",
                current_value=active_critical_incidents,
                expected_value=0,
                category="incidents",
            ),
            self._check(
                code="COMPONENT_ERRORS",
                passed=component_errors == 0,
                severity="critical",
                title="Erros de componentes",
                pass_message="Nenhum componente final reporta erro.",
                fail_message="Existem erros em componentes finais.",
                current_value=component_errors,
                expected_value=0,
                category="components",
            ),
            self._check(
                code="RUNTIME_FAILURES",
                passed=total_runtime_failures <= c.max_runtime_failures,
                severity="warning",
                title="Falhas acumuladas dos runtimes",
                pass_message="As falhas acumuladas estão dentro do limite.",
                fail_message="As falhas acumuladas excederam o limite.",
                current_value=total_runtime_failures,
                expected_value=f"<= {c.max_runtime_failures}",
                category="operations",
            ),
            self._check(
                code="PAPER_ONLY_SCOPE",
                passed=True,
                severity="critical",
                title="Escopo do gate",
                pass_message="O gate permanece restrito ao ambiente Paper.",
                fail_message="O gate não pode autorizar execução real.",
                current_value="PAPER_ASSURANCE_QUALIFICATION_ONLY",
                expected_value="PAPER_ASSURANCE_QUALIFICATION_ONLY",
                category="safety",
            ),
        ]

        failed_checks = [check for check in checks if check.status == "FAIL"]
        critical_failures = [
            check for check in failed_checks if check.severity == "critical"
        ]
        warning_failures = [
            check for check in failed_checks if check.severity == "warning"
        ]

        no_data = (
            history_entries < c.min_history_entries
            or assurance_status == "NO_DATA"
            or latest_history_status == "NO_DATA"
        )
        hard_blocked = (
            assurance_status == "BLOCKED"
            or latest_history_status == "BLOCKED"
            or integrity_status == "BROKEN"
            or monitor_status == "CRITICAL"
            or active_critical_incidents > 0
            or component_errors > 0
        )

        if hard_blocked:
            status = "BLOCKED"
        elif no_data:
            status = "NO_DATA"
        elif failed_checks:
            status = "PENDING"
        else:
            status = "QUALIFIED"

        passed_checks = sum(1 for check in checks if check.status == "PASS")
        qualification_score = round(
            passed_checks / len(checks) * 100 if checks else 0.0,
            2,
        )

        if status == "BLOCKED":
            qualification_score = min(qualification_score, 49.0)
        elif status == "NO_DATA":
            qualification_score = min(qualification_score, 59.0)
        elif status == "PENDING":
            qualification_score = min(qualification_score, 79.0)

        return {
            "status": status,
            "qualified": status == "QUALIFIED",
            "scope": "PAPER_ASSURANCE_QUALIFICATION_ONLY",
            "generated_at": _utc_now(),
            "qualification_score": qualification_score,
            "criteria": asdict(c),
            "summary": {
                "total_checks": len(checks),
                "passed_checks": passed_checks,
                "failed_checks": len(failed_checks),
                "critical_failures": len(critical_failures),
                "warning_failures": len(warning_failures),
                "assurance_status": assurance_status,
                "assurance_score": assurance_score,
                "history_entries": history_entries,
                "latest_history_status": latest_history_status,
                "latest_history_score": latest_history_score,
                "average_history_score": average_history_score,
                "current_streak_status": current_streak_status,
                "current_streak": current_streak,
                "integrity_status": integrity_status,
                "monitor_status": monitor_status,
                "active_incidents": active_incidents,
                "active_critical_incidents": active_critical_incidents,
                "component_errors": component_errors,
                "assurance_runtime_failures": assurance_runtime_failures,
                "history_runtime_failures": history_runtime_failures,
                "total_runtime_failures": total_runtime_failures,
                "history_runtime_status": runtime.get("status"),
            },
            "checks": [check.to_dict() for check in checks],
            "failures": [check.to_dict() for check in failed_checks],
            "components": {
                "assurance": dict(assurance),
                "history": dict(history),
                "history_runtime": dict(runtime),
            },
            "manual_start_required": True,
            **self._safe_flags(),
        }


final_paper_assurance_qualification_gate = (
    FinalPaperAssuranceQualificationGate()
)
