from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.certification_assurance_center import (
    PaperCertificationAssuranceCenter,
)
from app.paper.certification_assurance_gate import (
    PaperAssuranceQualificationGate,
)
from app.paper.certification_assurance_gate_history import (
    PaperAssuranceQualificationHistory,
)
from app.paper.certification_assurance_gate_history_runtime import (
    paper_assurance_gate_history_runtime,
)
from app.paper.certification_assurance_history_runtime import (
    paper_assurance_history_runtime,
)


def _utc_now() -> str:
    return datetime.now(
        timezone.utc
    ).isoformat()


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
    if value is None or isinstance(
        value,
        bool,
    ):
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
class FinalPaperValidationThresholds:
    min_gate_evaluations: int
    min_qualified_streak: int
    min_gate_score: float
    min_assurance_score: float
    max_runtime_failures: int

    @classmethod
    def from_env(
        cls,
    ) -> "FinalPaperValidationThresholds":
        return cls(
            min_gate_evaluations=max(
                1,
                _env_int(
                    "PAPER_FINAL_VALIDATION_MIN_GATE_EVALUATIONS",
                    3,
                ),
            ),
            min_qualified_streak=max(
                1,
                _env_int(
                    "PAPER_FINAL_VALIDATION_MIN_QUALIFIED_STREAK",
                    3,
                ),
            ),
            min_gate_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_VALIDATION_MIN_GATE_SCORE",
                        90.0,
                    ),
                ),
            ),
            min_assurance_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_FINAL_VALIDATION_MIN_ASSURANCE_SCORE",
                        90.0,
                    ),
                ),
            ),
            max_runtime_failures=max(
                0,
                _env_int(
                    "PAPER_FINAL_VALIDATION_MAX_RUNTIME_FAILURES",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class FinalPaperValidationCheck:
    code: str
    status: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None
    category: str = "validation"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class FinalPaperValidation:
    """Validação final, somente leitura, da jornada Paper."""

    def __init__(
        self,
        *,
        assurance_center: PaperCertificationAssuranceCenter | None = None,
        qualification_gate: PaperAssuranceQualificationGate | None = None,
        qualification_history: PaperAssuranceQualificationHistory | None = None,
        thresholds: FinalPaperValidationThresholds | None = None,
        assurance_runtime: Any | None = None,
        gate_runtime: Any | None = None,
    ) -> None:
        self.assurance_center = (
            assurance_center
            if assurance_center is not None
            else PaperCertificationAssuranceCenter()
        )

        self.qualification_gate = (
            qualification_gate
            if qualification_gate is not None
            else PaperAssuranceQualificationGate()
        )

        self.qualification_history = (
            qualification_history
            if qualification_history is not None
            else PaperAssuranceQualificationHistory()
        )

        self.thresholds = (
            thresholds
            if thresholds is not None
            else FinalPaperValidationThresholds.from_env()
        )

        self.assurance_runtime = (
            assurance_runtime
            if assurance_runtime is not None
            else paper_assurance_history_runtime
        )

        self.gate_runtime = (
            gate_runtime
            if gate_runtime is not None
            else paper_assurance_gate_history_runtime
        )

    @staticmethod
    def _safe_flags() -> dict[str, bool]:
        return {
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    @staticmethod
    def _validate_safe_payload(
        name: str,
        payload: Mapping[str, Any],
        *,
        require_read_only: bool = True,
    ) -> None:
        required_false = (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if payload.get(
                field
            ) is not False:
                raise RuntimeError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if (
            require_read_only
            and payload.get(
                "read_only"
            )
            is not True
        ):
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    @staticmethod
    def _check(
        *,
        code: str,
        passed: bool,
        title: str,
        pass_message: str,
        fail_message: str,
        current_value: Any,
        expected_value: Any,
        category: str,
    ) -> FinalPaperValidationCheck:
        return FinalPaperValidationCheck(
            code=code,
            status=(
                "PASS"
                if passed
                else "FAIL"
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
        assurance = (
            self.assurance_center
            .snapshot()
        )

        gate = (
            self.qualification_gate
            .evaluate()
        )

        history = (
            self.qualification_history
            .summary()
        )

        assurance_runtime = (
            self.assurance_runtime
            .status()
        )

        gate_runtime = (
            self.gate_runtime
            .status()
        )

        self._validate_safe_payload(
            "assurance",
            assurance,
        )

        self._validate_safe_payload(
            "gate",
            gate,
        )

        self._validate_safe_payload(
            "gate_history",
            history,
        )

        self._validate_safe_payload(
            "assurance_runtime",
            assurance_runtime,
            require_read_only=False,
        )

        self._validate_safe_payload(
            "gate_runtime",
            gate_runtime,
            require_read_only=False,
        )

        assurance_status = str(
            assurance.get(
                "status"
            )
            or "UNKNOWN"
        ).upper()

        assurance_score = _number(
            assurance.get(
                "assurance_score"
            )
        )

        gate_status = str(
            gate.get(
                "status"
            )
            or "INSUFFICIENT_DATA"
        ).upper()

        gate_score = _number(
            gate.get(
                "qualification_score"
            )
        )

        history_entries = _integer(
            history.get(
                "total_entries"
            )
        )

        history_latest_status = str(
            history.get(
                "latest_status"
            )
            or ""
        ).upper()

        qualified_streak = _integer(
            history.get(
                "current_streak"
            )
        )

        if (
            history_latest_status
            != "QUALIFIED"
        ):
            qualified_streak = 0

        assurance_runtime_failures = _integer(
            assurance_runtime.get(
                "failed_cycles"
            )
        )

        gate_runtime_failures = _integer(
            gate_runtime.get(
                "failed_cycles"
            )
        )

        total_runtime_failures = (
            assurance_runtime_failures
            + gate_runtime_failures
        )

        data_checks = [
            self._check(
                code="MIN_GATE_EVALUATIONS",
                passed=(
                    history_entries
                    >= self.thresholds.min_gate_evaluations
                ),
                title="Avaliações históricas do gate",
                pass_message=(
                    "O histórico possui avaliações suficientes."
                ),
                fail_message=(
                    "O histórico ainda não possui avaliações suficientes."
                ),
                current_value=history_entries,
                expected_value=(
                    self.thresholds.min_gate_evaluations
                ),
                category="data",
            ),
            self._check(
                code="LATEST_HISTORY_STATUS",
                passed=(
                    history_latest_status
                    == "QUALIFIED"
                ),
                title="Última avaliação histórica",
                pass_message=(
                    "A avaliação histórica mais recente está QUALIFIED."
                ),
                fail_message=(
                    "A avaliação histórica mais recente ainda não está QUALIFIED."
                ),
                current_value=(
                    history_latest_status
                    or None
                ),
                expected_value="QUALIFIED",
                category="data",
            ),
        ]

        validation_checks = [
            self._check(
                code="ASSURANCE_ASSURED",
                passed=(
                    assurance_status
                    == "ASSURED"
                ),
                title="Centro de Garantia",
                pass_message=(
                    "O Centro de Garantia está ASSURED."
                ),
                fail_message=(
                    "O Centro de Garantia ainda não está ASSURED."
                ),
                current_value=assurance_status,
                expected_value="ASSURED",
                category="validation",
            ),
            self._check(
                code="CURRENT_GATE_QUALIFIED",
                passed=(
                    gate_status
                    == "QUALIFIED"
                ),
                title="Gate atual",
                pass_message=(
                    "O Gate atual está QUALIFIED."
                ),
                fail_message=(
                    "O Gate atual ainda não está QUALIFIED."
                ),
                current_value=gate_status,
                expected_value="QUALIFIED",
                category="validation",
            ),
            self._check(
                code="QUALIFIED_STREAK",
                passed=(
                    qualified_streak
                    >= self.thresholds.min_qualified_streak
                ),
                title="Sequência histórica QUALIFIED",
                pass_message=(
                    "A sequência mínima de QUALIFIED foi alcançada."
                ),
                fail_message=(
                    "A sequência histórica de QUALIFIED ainda é insuficiente."
                ),
                current_value=qualified_streak,
                expected_value=(
                    self.thresholds.min_qualified_streak
                ),
                category="validation",
            ),
            self._check(
                code="GATE_SCORE",
                passed=(
                    gate_score
                    >= self.thresholds.min_gate_score
                ),
                title="Score do gate",
                pass_message=(
                    "O score do Gate atende ao mínimo."
                ),
                fail_message=(
                    "O score do Gate está abaixo do mínimo."
                ),
                current_value=gate_score,
                expected_value=(
                    self.thresholds.min_gate_score
                ),
                category="validation",
            ),
            self._check(
                code="ASSURANCE_SCORE",
                passed=(
                    assurance_score
                    >= self.thresholds.min_assurance_score
                ),
                title="Score do Centro de Garantia",
                pass_message=(
                    "O score de garantia atende ao mínimo."
                ),
                fail_message=(
                    "O score de garantia está abaixo do mínimo."
                ),
                current_value=assurance_score,
                expected_value=(
                    self.thresholds.min_assurance_score
                ),
                category="validation",
            ),
            self._check(
                code="RUNTIME_FAILURES",
                passed=(
                    total_runtime_failures
                    <= self.thresholds.max_runtime_failures
                ),
                title="Falhas acumuladas dos runtimes",
                pass_message=(
                    "As falhas dos runtimes estão dentro do limite."
                ),
                fail_message=(
                    "Existem falhas de runtime além do limite."
                ),
                current_value=total_runtime_failures,
                expected_value=(
                    self.thresholds.max_runtime_failures
                ),
                category="operations",
            ),
            self._check(
                code="PAPER_ONLY_SCOPE",
                passed=True,
                title="Escopo final",
                pass_message=(
                    "A validação final é restrita ao ambiente Paper."
                ),
                fail_message=(
                    "A validação final não pode autorizar execução live."
                ),
                current_value=(
                    "PAPER_VALIDATION_ONLY"
                ),
                expected_value=(
                    "PAPER_VALIDATION_ONLY"
                ),
                category="safety",
            ),
        ]

        checks = (
            data_checks
            + validation_checks
        )

        failed_data = [
            item
            for item in data_checks
            if item.status == "FAIL"
        ]

        failed_validation = [
            item
            for item in validation_checks
            if item.status == "FAIL"
        ]

        blocking_statuses = {
            "CRITICAL",
            "BLOCKED",
        }

        hard_blocked = (
            assurance_status
            in blocking_statuses
            or gate_status
            == "NOT_QUALIFIED"
            or total_runtime_failures
            > self.thresholds.max_runtime_failures
        )

        if failed_data:
            status = "INSUFFICIENT_DATA"

        elif hard_blocked:
            status = "PAPER_BLOCKED"

        elif failed_validation:
            status = "PAPER_PENDING"

        else:
            status = "PAPER_VALIDATED"

        passed_checks = sum(
            1
            for item in checks
            if item.status == "PASS"
        )

        validation_score = round(
            (
                passed_checks
                / len(checks)
                * 100
            )
            if checks
            else 0.0,
            2,
        )

        if status == "INSUFFICIENT_DATA":
            validation_score = min(
                validation_score,
                69.0,
            )

        elif status == "PAPER_BLOCKED":
            validation_score = min(
                validation_score,
                49.0,
            )

        elif status == "PAPER_PENDING":
            validation_score = min(
                validation_score,
                79.0,
            )

        return {
            "status": status,
            "validated": (
                status
                == "PAPER_VALIDATED"
            ),
            "scope": (
                "PAPER_VALIDATION_ONLY"
            ),
            "generated_at": _utc_now(),
            "validation_score": (
                validation_score
            ),
            "thresholds": asdict(
                self.thresholds
            ),
            "summary": {
                "total_checks": len(
                    checks
                ),
                "passed_checks": (
                    passed_checks
                ),
                "failed_checks": (
                    len(checks)
                    - passed_checks
                ),
                "failed_data_checks": (
                    len(failed_data)
                ),
                "failed_validation_checks": (
                    len(
                        failed_validation
                    )
                ),
                "assurance_status": (
                    assurance_status
                ),
                "assurance_score": (
                    assurance_score
                ),
                "gate_status": (
                    gate_status
                ),
                "gate_score": (
                    gate_score
                ),
                "gate_history_entries": (
                    history_entries
                ),
                "gate_history_latest_status": (
                    history_latest_status
                    or None
                ),
                "qualified_streak": (
                    qualified_streak
                ),
                "assurance_runtime_status": (
                    assurance_runtime.get(
                        "status"
                    )
                ),
                "gate_runtime_status": (
                    gate_runtime.get(
                        "status"
                    )
                ),
                "assurance_runtime_failures": (
                    assurance_runtime_failures
                ),
                "gate_runtime_failures": (
                    gate_runtime_failures
                ),
                "total_runtime_failures": (
                    total_runtime_failures
                ),
            },
            "checks": [
                item.to_dict()
                for item in checks
            ],
            "failures": [
                item.to_dict()
                for item in checks
                if item.status == "FAIL"
            ],
            "components": {
                "assurance": assurance,
                "gate": gate,
                "gate_history": history,
                "assurance_runtime": (
                    assurance_runtime
                ),
                "gate_runtime": (
                    gate_runtime
                ),
            },
            "manual_start_required": True,
            "next_step_authorized": False,
            **self._safe_flags(),
        }


final_paper_validation = (
    FinalPaperValidation()
)
