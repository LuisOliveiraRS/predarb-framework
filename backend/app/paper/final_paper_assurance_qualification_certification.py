from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from app.paper.final_paper_assurance_qualification_gate import (
    final_paper_assurance_qualification_gate,
)
from app.paper.final_paper_assurance_qualification_gate_history import (
    FinalPaperAssuranceQualificationGateHistory,
)
from app.paper.final_paper_assurance_qualification_gate_history_runtime import (
    final_paper_assurance_qualification_gate_history_runtime,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


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


@dataclass(frozen=True)
class FinalPaperQualificationCertificationCriteria:
    min_gate_history_entries: int
    min_qualified_streak: int
    min_current_gate_score: float
    min_average_gate_score: float
    max_gate_runtime_failures: int

    @classmethod
    def from_env(
        cls,
    ) -> "FinalPaperQualificationCertificationCriteria":
        return cls(
            min_gate_history_entries=max(
                1,
                _env_int(
                    "PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_HISTORY_ENTRIES",
                    3,
                ),
            ),
            min_qualified_streak=max(
                1,
                _env_int(
                    "PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_STREAK",
                    3,
                ),
            ),
            min_current_gate_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_CURRENT_SCORE",
                        90.0,
                    ),
                ),
            ),
            min_average_gate_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_QUALIFICATION_CERTIFICATION_MIN_AVERAGE_SCORE",
                        90.0,
                    ),
                ),
            ),
            max_gate_runtime_failures=max(
                0,
                _env_int(
                    "PAPER_FINAL_QUALIFICATION_CERTIFICATION_MAX_RUNTIME_FAILURES",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class FinalPaperQualificationCertificationCheck:
    code: str
    status: str
    severity: str
    title: str
    message: str
    current_value: Any
    expected_value: Any
    category: str

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class FinalPaperAssuranceQualificationCertification:
    """Certificação técnica final e somente leitura do ambiente Paper."""

    def __init__(
        self,
        *,
        gate_provider: Any = (
            final_paper_assurance_qualification_gate
        ),
        gate_history_factory: Callable[
            [],
            FinalPaperAssuranceQualificationGateHistory,
        ] = FinalPaperAssuranceQualificationGateHistory,
        gate_history_runtime: Any = (
            final_paper_assurance_qualification_gate_history_runtime
        ),
        criteria: (
            FinalPaperQualificationCertificationCriteria
            | None
        ) = None,
    ) -> None:
        self.gate_provider = gate_provider
        self.gate_history_factory = gate_history_factory
        self.gate_history_runtime = gate_history_runtime
        self.criteria = (
            criteria
            if criteria is not None
            else (
                FinalPaperQualificationCertificationCriteria
                .from_env()
            )
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

        if (
            require_read_only
            and payload.get("read_only") is not True
        ):
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
    ) -> FinalPaperQualificationCertificationCheck:
        return FinalPaperQualificationCertificationCheck(
            code=code,
            status=(
                "PASS"
                if passed
                else "FAIL"
            ),
            severity=(
                "none"
                if passed
                else severity
            ),
            title=title,
            message=(
                pass_message
                if passed
                else fail_message
            ),
            current_value=current_value,
            expected_value=expected_value,
            category=category,
        )

    def evaluate(
        self,
    ) -> dict[str, Any]:
        gate = (
            self.gate_provider
            .evaluate()
        )

        history = (
            self.gate_history_factory()
            .summary()
        )

        runtime = (
            self.gate_history_runtime
            .status()
        )

        if not isinstance(
            gate,
            Mapping,
        ):
            raise RuntimeError(
                "O gate de qualificação não retornou um objeto."
            )

        if not isinstance(
            history,
            Mapping,
        ):
            raise RuntimeError(
                "O histórico do gate não retornou um objeto."
            )

        if not isinstance(
            runtime,
            Mapping,
        ):
            raise RuntimeError(
                "O runtime do histórico do gate não retornou um objeto."
            )

        self._validate_safe_payload(
            "qualification_gate",
            gate,
        )

        self._validate_safe_payload(
            "qualification_gate_history",
            history,
        )

        self._validate_safe_payload(
            "qualification_gate_history_runtime",
            runtime,
            require_read_only=False,
        )

        if (
            gate.get("scope")
            != "PAPER_ASSURANCE_QUALIFICATION_ONLY"
        ):
            raise RuntimeError(
                "Escopo do gate de qualificação inválido."
            )

        gate_status = str(
            gate.get("status")
            or "NO_DATA"
        ).upper()

        gate_score = _number(
            gate.get(
                "qualification_score"
            )
        )

        gate_summary = (
            gate.get("summary")
            or {}
        )

        history_entries = _integer(
            history.get(
                "total_entries"
            )
        )

        latest_status = str(
            history.get(
                "latest_status"
            )
            or "NO_DATA"
        ).upper()

        latest_score = _number(
            history.get(
                "latest_score"
            )
        )

        average_score = _number(
            history.get(
                "average_score"
            )
        )

        streak_status = str(
            history.get(
                "current_streak_status"
            )
            or "NO_DATA"
        ).upper()

        current_streak = _integer(
            history.get(
                "current_streak"
            )
        )

        longest_qualified_streak = _integer(
            history.get(
                "longest_qualified_streak"
            )
        )

        runtime_failures = _integer(
            runtime.get(
                "failed_cycles"
            )
        )

        critical_gate_failures = _integer(
            gate_summary.get(
                "critical_failures"
            )
        )

        checks = [
            self._check(
                code="CURRENT_GATE_QUALIFIED",
                passed=(
                    gate_status
                    == "QUALIFIED"
                ),
                severity=(
                    "critical"
                    if gate_status
                    == "BLOCKED"
                    else "warning"
                ),
                title="Gate atual",
                pass_message=(
                    "O gate atual está QUALIFIED."
                ),
                fail_message=(
                    "O gate atual ainda não está QUALIFIED."
                ),
                current_value=gate_status,
                expected_value="QUALIFIED",
                category="gate",
            ),
            self._check(
                code="CURRENT_GATE_SCORE",
                passed=(
                    gate_score
                    >= self.criteria.min_current_gate_score
                ),
                severity="warning",
                title="Score atual do gate",
                pass_message=(
                    "O score atual do gate atende ao mínimo."
                ),
                fail_message=(
                    "O score atual do gate está abaixo do mínimo."
                ),
                current_value=gate_score,
                expected_value=(
                    f">= "
                    f"{self.criteria.min_current_gate_score}"
                ),
                category="gate",
            ),
            self._check(
                code="GATE_HISTORY_VOLUME",
                passed=(
                    history_entries
                    >= self.criteria.min_gate_history_entries
                ),
                severity="warning",
                title="Volume do histórico do gate",
                pass_message=(
                    "O histórico do gate possui volume suficiente."
                ),
                fail_message=(
                    "O histórico do gate ainda possui volume insuficiente."
                ),
                current_value=history_entries,
                expected_value=(
                    f">= "
                    f"{self.criteria.min_gate_history_entries}"
                ),
                category="history",
            ),
            self._check(
                code="LATEST_GATE_STATUS",
                passed=(
                    latest_status
                    == "QUALIFIED"
                ),
                severity=(
                    "critical"
                    if latest_status
                    == "BLOCKED"
                    else "warning"
                ),
                title="Último gate persistido",
                pass_message=(
                    "O último gate persistido está QUALIFIED."
                ),
                fail_message=(
                    "O último gate persistido ainda não está QUALIFIED."
                ),
                current_value=latest_status,
                expected_value="QUALIFIED",
                category="history",
            ),
            self._check(
                code="LATEST_GATE_SCORE",
                passed=(
                    latest_score
                    >= self.criteria.min_current_gate_score
                ),
                severity="warning",
                title="Último score persistido",
                pass_message=(
                    "O último score persistido atende ao mínimo."
                ),
                fail_message=(
                    "O último score persistido está abaixo do mínimo."
                ),
                current_value=latest_score,
                expected_value=(
                    f">= "
                    f"{self.criteria.min_current_gate_score}"
                ),
                category="history",
            ),
            self._check(
                code="AVERAGE_GATE_SCORE",
                passed=(
                    average_score
                    >= self.criteria.min_average_gate_score
                ),
                severity="warning",
                title="Score médio do gate",
                pass_message=(
                    "O score médio do gate atende ao mínimo."
                ),
                fail_message=(
                    "O score médio do gate está abaixo do mínimo."
                ),
                current_value=average_score,
                expected_value=(
                    f">= "
                    f"{self.criteria.min_average_gate_score}"
                ),
                category="stability",
            ),
            self._check(
                code="QUALIFIED_STREAK",
                passed=(
                    streak_status
                    == "QUALIFIED"
                    and current_streak
                    >= self.criteria.min_qualified_streak
                ),
                severity="warning",
                title="Sequência atual QUALIFIED",
                pass_message=(
                    "A sequência atual QUALIFIED atende ao mínimo."
                ),
                fail_message=(
                    "A sequência atual QUALIFIED ainda é insuficiente."
                ),
                current_value={
                    "status": streak_status,
                    "streak": current_streak,
                },
                expected_value={
                    "status": "QUALIFIED",
                    "streak": (
                        f">= "
                        f"{self.criteria.min_qualified_streak}"
                    ),
                },
                category="stability",
            ),
            self._check(
                code="GATE_CRITICAL_FAILURES",
                passed=(
                    critical_gate_failures
                    == 0
                ),
                severity="critical",
                title="Falhas críticas do gate",
                pass_message=(
                    "O gate não possui falhas críticas."
                ),
                fail_message=(
                    "O gate possui falhas críticas."
                ),
                current_value=critical_gate_failures,
                expected_value=0,
                category="gate",
            ),
            self._check(
                code="GATE_RUNTIME_FAILURES",
                passed=(
                    runtime_failures
                    <= self.criteria.max_gate_runtime_failures
                ),
                severity="warning",
                title="Falhas do runtime do gate",
                pass_message=(
                    "As falhas do runtime estão dentro do limite."
                ),
                fail_message=(
                    "As falhas do runtime excederam o limite."
                ),
                current_value=runtime_failures,
                expected_value=(
                    f"<= "
                    f"{self.criteria.max_gate_runtime_failures}"
                ),
                category="operations",
            ),
            self._check(
                code="PAPER_CERTIFICATION_SCOPE",
                passed=True,
                severity="critical",
                title="Escopo da certificação",
                pass_message=(
                    "A certificação permanece restrita ao ambiente Paper."
                ),
                fail_message=(
                    "A certificação não pode autorizar execução real."
                ),
                current_value=(
                    "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
                ),
                expected_value=(
                    "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
                ),
                category="safety",
            ),
        ]

        failed_checks = [
            check
            for check in checks
            if check.status == "FAIL"
        ]

        critical_failures = [
            check
            for check in failed_checks
            if check.severity == "critical"
        ]

        warning_failures = [
            check
            for check in failed_checks
            if check.severity == "warning"
        ]

        no_data = (
            history_entries
            < self.criteria.min_gate_history_entries
            or gate_status
            == "NO_DATA"
            or latest_status
            == "NO_DATA"
        )

        hard_blocked = (
            gate_status
            == "BLOCKED"
            or latest_status
            == "BLOCKED"
            or critical_gate_failures
            > 0
        )

        if hard_blocked:
            status = "BLOCKED"

        elif no_data:
            status = "NO_DATA"

        elif failed_checks:
            status = "PENDING"

        else:
            status = "CERTIFIED"

        passed_checks = sum(
            1
            for check in checks
            if check.status == "PASS"
        )

        certification_score = round(
            (
                passed_checks
                / len(checks)
                * 100
            )
            if checks
            else 0.0,
            2,
        )

        if status == "BLOCKED":
            certification_score = min(
                certification_score,
                49.0,
            )

        elif status == "NO_DATA":
            certification_score = min(
                certification_score,
                59.0,
            )

        elif status == "PENDING":
            certification_score = min(
                certification_score,
                79.0,
            )

        return {
            "status": status,
            "certified": (
                status == "CERTIFIED"
            ),
            "scope": (
                "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
            ),
            "generated_at": _utc_now(),
            "certification_score": (
                certification_score
            ),
            "criteria": asdict(
                self.criteria
            ),
            "summary": {
                "total_checks": len(checks),
                "passed_checks": passed_checks,
                "failed_checks": len(
                    failed_checks
                ),
                "critical_failures": len(
                    critical_failures
                ),
                "warning_failures": len(
                    warning_failures
                ),
                "gate_status": gate_status,
                "gate_score": gate_score,
                "gate_history_entries": history_entries,
                "latest_gate_status": latest_status,
                "latest_gate_score": latest_score,
                "average_gate_score": average_score,
                "current_streak_status": streak_status,
                "current_streak": current_streak,
                "longest_qualified_streak": (
                    longest_qualified_streak
                ),
                "gate_runtime_status": runtime.get(
                    "status"
                ),
                "gate_runtime_running": runtime.get(
                    "running"
                ),
                "gate_runtime_failures": runtime_failures,
                "gate_critical_failures": (
                    critical_gate_failures
                ),
            },
            "checks": [
                check.to_dict()
                for check in checks
            ],
            "failures": [
                check.to_dict()
                for check in failed_checks
            ],
            "components": {
                "gate": dict(gate),
                "gate_history": dict(history),
                "gate_history_runtime": dict(runtime),
            },
            "manual_start_required": True,
            **self._safe_flags(),
        }


final_paper_assurance_qualification_certification = (
    FinalPaperAssuranceQualificationCertification()
)
