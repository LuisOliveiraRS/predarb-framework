from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Mapping

from app.paper.final_paper_validation import (
    final_paper_validation,
)
from app.paper.final_paper_validation_evidence import (
    FinalPaperValidationEvidence,
)
from app.paper.final_paper_validation_evidence_incident_runtime import (
    final_paper_evidence_incident_runtime,
)
from app.paper.final_paper_validation_evidence_incidents import (
    FinalPaperEvidenceIncidentJournal,
)
from app.paper.final_paper_validation_evidence_monitor import (
    final_paper_validation_evidence_monitor,
)
from app.paper.final_paper_validation_history import (
    FinalPaperValidationHistory,
)
from app.paper.final_paper_validation_history_runtime import (
    final_paper_validation_history_runtime,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _integer(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return float(default)

    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


@dataclass(frozen=True)
class FinalPaperAssuranceCheck:
    code: str
    status: str
    severity: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None
    category: str = "assurance"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalPaperOperationalAssurance:
    """Centro final de garantia operacional, somente leitura, do ambiente Paper."""

    def __init__(
        self,
        *,
        validation_provider: Any = final_paper_validation,
        validation_history_factory: Callable[
            [],
            FinalPaperValidationHistory,
        ] = FinalPaperValidationHistory,
        validation_runtime: Any = final_paper_validation_history_runtime,
        evidence_factory: Callable[
            [],
            FinalPaperValidationEvidence,
        ] = FinalPaperValidationEvidence,
        evidence_monitor: Any = final_paper_validation_evidence_monitor,
        incident_journal_factory: Callable[
            [],
            FinalPaperEvidenceIncidentJournal,
        ] = FinalPaperEvidenceIncidentJournal,
        incident_runtime: Any = final_paper_evidence_incident_runtime,
    ) -> None:
        self.validation_provider = validation_provider
        self.validation_history_factory = validation_history_factory
        self.validation_runtime = validation_runtime
        self.evidence_factory = evidence_factory
        self.evidence_monitor = evidence_monitor
        self.incident_journal_factory = incident_journal_factory
        self.incident_runtime = incident_runtime

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
    ) -> FinalPaperAssuranceCheck:
        return FinalPaperAssuranceCheck(
            code=code,
            status="PASS" if passed else "FAIL",
            severity="none" if passed else severity,
            title=title,
            message=pass_message if passed else fail_message,
            current_value=current_value,
            expected_value=expected_value,
            category=category,
        )

    @staticmethod
    def _collect(
        name: str,
        callback: Callable[[], Mapping[str, Any]],
    ) -> tuple[dict[str, Any], str | None]:
        try:
            payload = callback()

            if not isinstance(payload, Mapping):
                raise RuntimeError(
                    f"{name}: resposta não é um objeto."
                )

            return dict(payload), None

        except Exception as exc:
            return {}, str(exc)

    def evaluate(self) -> dict[str, Any]:
        components: dict[str, dict[str, Any]] = {}
        component_errors: dict[str, str] = {}

        providers: tuple[
            tuple[
                str,
                Callable[[], Mapping[str, Any]],
                bool,
            ],
            ...,
        ] = (
            (
                "validation",
                self.validation_provider.evaluate,
                True,
            ),
            (
                "validation_history",
                self.validation_history_factory().summary,
                True,
            ),
            (
                "validation_runtime",
                self.validation_runtime.status,
                False,
            ),
            (
                "evidence_summary",
                self.evidence_factory().summary,
                True,
            ),
            (
                "evidence_integrity",
                self.evidence_factory().verify,
                True,
            ),
            (
                "evidence_monitor",
                self.evidence_monitor.evaluate,
                True,
            ),
            (
                "incident_journal",
                self.incident_journal_factory().summary,
                True,
            ),
            (
                "incident_runtime",
                self.incident_runtime.status,
                False,
            ),
        )

        for name, callback, require_read_only in providers:
            payload, error = self._collect(
                name,
                callback,
            )

            if error is not None:
                component_errors[name] = error
                continue

            self._validate_safe_payload(
                name,
                payload,
                require_read_only=require_read_only,
            )

            components[name] = payload

        validation = components.get(
            "validation",
            {},
        )
        validation_history = components.get(
            "validation_history",
            {},
        )
        validation_runtime = components.get(
            "validation_runtime",
            {},
        )
        evidence_summary = components.get(
            "evidence_summary",
            {},
        )
        evidence_integrity = components.get(
            "evidence_integrity",
            {},
        )
        evidence_monitor = components.get(
            "evidence_monitor",
            {},
        )
        incident_journal = components.get(
            "incident_journal",
            {},
        )
        incident_runtime = components.get(
            "incident_runtime",
            {},
        )

        validation_status = str(
            validation.get("status")
            or "INSUFFICIENT_DATA"
        ).upper()

        history_entries = _integer(
            validation_history.get(
                "total_entries"
            )
        )

        evidence_entries = _integer(
            evidence_summary.get(
                "total_entries"
            )
        )

        integrity_status = str(
            evidence_integrity.get(
                "integrity_status"
            )
            or evidence_summary.get(
                "integrity_status"
            )
            or "EMPTY"
        ).upper()

        monitor_status = str(
            evidence_monitor.get("status")
            or "NO_DATA"
        ).upper()

        active_incidents = _integer(
            incident_journal.get(
                "active_incidents"
            )
        )

        active_critical = _integer(
            incident_journal.get(
                "active_critical"
            )
        )

        validation_runtime_failures = _integer(
            validation_runtime.get(
                "failed_cycles"
            )
        )

        incident_runtime_failures = _integer(
            incident_runtime.get(
                "failed_cycles"
            )
        )

        total_runtime_failures = (
            validation_runtime_failures
            + incident_runtime_failures
        )

        checks = [
            self._check(
                code="COMPONENTS_AVAILABLE",
                passed=not component_errors,
                severity="critical",
                title="Disponibilidade dos componentes",
                pass_message=(
                    "Todos os componentes finais responderam."
                ),
                fail_message=(
                    "Um ou mais componentes finais não puderam ser avaliados."
                ),
                current_value=(
                    sorted(component_errors)
                    if component_errors
                    else []
                ),
                expected_value=[],
                category="components",
            ),
            self._check(
                code="FINAL_VALIDATION",
                passed=(
                    validation_status
                    == "PAPER_VALIDATED"
                ),
                severity=(
                    "critical"
                    if validation_status
                    == "PAPER_BLOCKED"
                    else "warning"
                ),
                title="Validação final Paper",
                pass_message=(
                    "A validação final está PAPER_VALIDATED."
                ),
                fail_message=(
                    "A validação final ainda não está PAPER_VALIDATED."
                ),
                current_value=validation_status,
                expected_value="PAPER_VALIDATED",
                category="validation",
            ),
            self._check(
                code="VALIDATION_HISTORY",
                passed=history_entries > 0,
                severity="warning",
                title="Histórico da validação final",
                pass_message=(
                    "Existe histórico persistente da validação final."
                ),
                fail_message=(
                    "Ainda não existe histórico persistente da validação final."
                ),
                current_value=history_entries,
                expected_value=">= 1",
                category="history",
            ),
            self._check(
                code="EVIDENCE_AVAILABLE",
                passed=evidence_entries > 0,
                severity="warning",
                title="Evidências finais",
                pass_message=(
                    "Existe ao menos uma evidência final persistida."
                ),
                fail_message=(
                    "Ainda não existe evidência final persistida."
                ),
                current_value=evidence_entries,
                expected_value=">= 1",
                category="evidence",
            ),
            self._check(
                code="EVIDENCE_INTEGRITY",
                passed=integrity_status == "VALID",
                severity="critical",
                title="Integridade probatória",
                pass_message=(
                    "A cadeia SHA-256 das evidências está VALID."
                ),
                fail_message=(
                    "A cadeia de evidências não está em estado VALID."
                ),
                current_value=integrity_status,
                expected_value="VALID",
                category="evidence",
            ),
            self._check(
                code="EVIDENCE_MONITOR",
                passed=monitor_status == "HEALTHY",
                severity=(
                    "critical"
                    if monitor_status == "CRITICAL"
                    else "warning"
                ),
                title="Monitor das evidências",
                pass_message=(
                    "O monitor das evidências está HEALTHY."
                ),
                fail_message=(
                    "O monitor das evidências ainda não está HEALTHY."
                ),
                current_value=monitor_status,
                expected_value="HEALTHY",
                category="monitoring",
            ),
            self._check(
                code="ACTIVE_CRITICAL_INCIDENTS",
                passed=active_critical == 0,
                severity="critical",
                title="Incidentes críticos ativos",
                pass_message=(
                    "Não existem incidentes críticos ativos."
                ),
                fail_message=(
                    "Existem incidentes críticos ativos."
                ),
                current_value=active_critical,
                expected_value=0,
                category="incidents",
            ),
            self._check(
                code="ACTIVE_INCIDENTS",
                passed=active_incidents == 0,
                severity="warning",
                title="Incidentes ativos",
                pass_message=(
                    "Não existem incidentes ativos."
                ),
                fail_message=(
                    "Existem incidentes ativos no diário."
                ),
                current_value=active_incidents,
                expected_value=0,
                category="incidents",
            ),
            self._check(
                code="RUNTIME_FAILURES",
                passed=total_runtime_failures == 0,
                severity="warning",
                title="Falhas dos runtimes finais",
                pass_message=(
                    "Os runtimes finais não registram falhas."
                ),
                fail_message=(
                    "Existem falhas acumuladas nos runtimes finais."
                ),
                current_value=total_runtime_failures,
                expected_value=0,
                category="operations",
            ),
            self._check(
                code="PAPER_ONLY_SCOPE",
                passed=True,
                severity="critical",
                title="Escopo operacional",
                pass_message=(
                    "O Centro Final permanece restrito ao ambiente Paper."
                ),
                fail_message=(
                    "O Centro Final não pode autorizar execução real."
                ),
                current_value="PAPER_ASSURANCE_ONLY",
                expected_value="PAPER_ASSURANCE_ONLY",
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
            history_entries == 0
            or evidence_entries == 0
            or validation_status
            == "INSUFFICIENT_DATA"
        )

        hard_blocked = (
            bool(component_errors)
            or validation_status
            == "PAPER_BLOCKED"
            or integrity_status
            == "BROKEN"
            or monitor_status
            == "CRITICAL"
            or active_critical > 0
        )

        if hard_blocked:
            status = "BLOCKED"

        elif no_data:
            status = "NO_DATA"

        elif failed_checks:
            status = "WARNING"

        else:
            status = "ASSURED"

        passed_checks = sum(
            1
            for check in checks
            if check.status == "PASS"
        )

        score = round(
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
            score = min(score, 49.0)

        elif status == "NO_DATA":
            score = min(score, 59.0)

        elif status == "WARNING":
            score = min(score, 79.0)

        return {
            "status": status,
            "assured": status == "ASSURED",
            "scope": "PAPER_ASSURANCE_ONLY",
            "generated_at": _utc_now(),
            "assurance_score": score,
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
                "component_errors": len(
                    component_errors
                ),
                "validation_status": validation_status,
                "validation_score": _number(
                    validation.get(
                        "validation_score"
                    )
                ),
                "validation_history_entries": history_entries,
                "evidence_entries": evidence_entries,
                "integrity_status": integrity_status,
                "monitor_status": monitor_status,
                "monitor_score": _number(
                    evidence_monitor.get(
                        "score"
                    )
                ),
                "active_incidents": active_incidents,
                "active_critical_incidents": active_critical,
                "validation_runtime_status": (
                    validation_runtime.get(
                        "status"
                    )
                ),
                "incident_runtime_status": (
                    incident_runtime.get(
                        "status"
                    )
                ),
                "total_runtime_failures": total_runtime_failures,
            },
            "checks": [
                check.to_dict()
                for check in checks
            ],
            "failures": [
                check.to_dict()
                for check in failed_checks
            ],
            "component_errors": component_errors,
            "components": components,
            "manual_start_required": True,
            **self._safe_flags(),
        }


final_paper_operational_assurance = (
    FinalPaperOperationalAssurance()
)
