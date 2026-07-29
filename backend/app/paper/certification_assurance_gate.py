from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.certification_assurance_history import (
    PaperCertificationAssuranceHistory,
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
class AssuranceGateThresholds:
    min_entries: int
    min_assured_streak: int
    recent_window: int
    min_latest_score: float
    min_recent_average_score: float
    max_recent_warning: int
    max_recent_blocked: int
    max_recent_critical: int

    @classmethod
    def from_env(
        cls,
    ) -> "AssuranceGateThresholds":
        min_entries = max(
            1,
            _env_int(
                "PAPER_ASSURANCE_GATE_MIN_ENTRIES",
                5,
            ),
        )

        min_assured_streak = max(
            1,
            _env_int(
                "PAPER_ASSURANCE_GATE_MIN_ASSURED_STREAK",
                3,
            ),
        )

        recent_window = max(
            min_assured_streak,
            _env_int(
                "PAPER_ASSURANCE_GATE_RECENT_WINDOW",
                5,
            ),
        )

        return cls(
            min_entries=min_entries,
            min_assured_streak=min_assured_streak,
            recent_window=recent_window,
            min_latest_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_ASSURANCE_GATE_MIN_LATEST_SCORE",
                        85.0,
                    ),
                ),
            ),
            min_recent_average_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_ASSURANCE_GATE_MIN_RECENT_AVERAGE_SCORE",
                        80.0,
                    ),
                ),
            ),
            max_recent_warning=max(
                0,
                _env_int(
                    "PAPER_ASSURANCE_GATE_MAX_RECENT_WARNING",
                    1,
                ),
            ),
            max_recent_blocked=max(
                0,
                _env_int(
                    "PAPER_ASSURANCE_GATE_MAX_RECENT_BLOCKED",
                    0,
                ),
            ),
            max_recent_critical=max(
                0,
                _env_int(
                    "PAPER_ASSURANCE_GATE_MAX_RECENT_CRITICAL",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class AssuranceGateCheck:
    code: str
    status: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None
    category: str = "qualification"

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class PaperAssuranceQualificationGate:
    """Gate somente leitura baseado no histórico do Centro de Garantia."""

    VALID_HISTORY_STATUSES = {
        "ASSURED",
        "WARNING",
        "PENDING",
        "BLOCKED",
        "CRITICAL",
        "UNKNOWN",
    }

    def __init__(
        self,
        *,
        history: PaperCertificationAssuranceHistory | None = None,
        thresholds: AssuranceGateThresholds | None = None,
    ) -> None:
        self.history = (
            history
            if history is not None
            else PaperCertificationAssuranceHistory()
        )

        self.thresholds = (
            thresholds
            if thresholds is not None
            else AssuranceGateThresholds.from_env()
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

    @classmethod
    def _validate_safe_payload(
        cls,
        name: str,
        payload: Mapping[str, Any],
    ) -> None:
        required_false = (
            "paper_execution_authorized",
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

    @staticmethod
    def _consecutive_assured(
        entries: list[Mapping[str, Any]],
    ) -> int:
        count = 0

        for entry in entries:
            if str(
                entry.get("status") or ""
            ).upper() == "ASSURED":
                count += 1
            else:
                break

        return count

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
    ) -> AssuranceGateCheck:
        return AssuranceGateCheck(
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
        summary = self.history.summary()

        self._validate_safe_payload(
            "history_summary",
            summary,
        )

        entries = self.history.list_entries(
            limit=self.thresholds.recent_window
        )

        for index, entry in enumerate(entries):
            self._validate_safe_payload(
                f"history_entry_{index}",
                entry,
            )

            status = str(
                entry.get("status") or ""
            ).upper()

            if status not in self.VALID_HISTORY_STATUSES:
                raise RuntimeError(
                    f"history_entry_{index}: status inválido."
                )

        total_entries = _integer(
            summary.get("total_entries")
        )

        latest = (
            entries[0]
            if entries
            else None
        )

        latest_status = (
            str(
                latest.get("status") or ""
            ).upper()
            if latest
            else None
        )

        latest_score = (
            _number(
                latest.get("assurance_score")
            )
            if latest
            else 0.0
        )

        recent_scores = [
            _number(
                item.get("assurance_score")
            )
            for item in entries
        ]

        recent_average = (
            round(
                sum(recent_scores)
                / len(recent_scores),
                8,
            )
            if recent_scores
            else 0.0
        )

        assured_streak = (
            self._consecutive_assured(
                entries
            )
        )

        recent_warning = sum(
            1
            for item in entries
            if str(
                item.get("status") or ""
            ).upper() == "WARNING"
        )

        recent_blocked = sum(
            1
            for item in entries
            if str(
                item.get("status") or ""
            ).upper() == "BLOCKED"
        )

        recent_critical = sum(
            1
            for item in entries
            if str(
                item.get("status") or ""
            ).upper() == "CRITICAL"
        )

        data_checks = [
            self._check(
                code="MIN_HISTORY_ENTRIES",
                passed=(
                    total_entries
                    >= self.thresholds.min_entries
                ),
                title="Quantidade de snapshots",
                pass_message=(
                    "O histórico possui snapshots suficientes."
                ),
                fail_message=(
                    "O histórico ainda não possui snapshots suficientes."
                ),
                current_value=total_entries,
                expected_value=self.thresholds.min_entries,
                category="data",
            ),
            self._check(
                code="MIN_RECENT_WINDOW",
                passed=(
                    len(entries)
                    >= min(
                        self.thresholds.recent_window,
                        self.thresholds.min_entries,
                    )
                ),
                title="Janela recente disponível",
                pass_message=(
                    "A janela recente possui dados suficientes."
                ),
                fail_message=(
                    "A janela recente ainda está incompleta."
                ),
                current_value=len(entries),
                expected_value=min(
                    self.thresholds.recent_window,
                    self.thresholds.min_entries,
                ),
                category="data",
            ),
        ]

        qualification_checks = [
            self._check(
                code="LATEST_STATUS_ASSURED",
                passed=(
                    latest_status == "ASSURED"
                ),
                title="Último status consolidado",
                pass_message=(
                    "O snapshot mais recente está ASSURED."
                ),
                fail_message=(
                    "O snapshot mais recente ainda não está ASSURED."
                ),
                current_value=latest_status,
                expected_value="ASSURED",
                category="qualification",
            ),
            self._check(
                code="ASSURED_STREAK",
                passed=(
                    assured_streak
                    >= self.thresholds.min_assured_streak
                ),
                title="Sequência consecutiva ASSURED",
                pass_message=(
                    "A sequência mínima de ASSURED foi alcançada."
                ),
                fail_message=(
                    "A sequência de ASSURED ainda é insuficiente."
                ),
                current_value=assured_streak,
                expected_value=self.thresholds.min_assured_streak,
                category="qualification",
            ),
            self._check(
                code="LATEST_SCORE",
                passed=(
                    latest_score
                    >= self.thresholds.min_latest_score
                ),
                title="Score mais recente",
                pass_message=(
                    "O score mais recente atende ao mínimo."
                ),
                fail_message=(
                    "O score mais recente está abaixo do mínimo."
                ),
                current_value=latest_score,
                expected_value=self.thresholds.min_latest_score,
                category="qualification",
            ),
            self._check(
                code="RECENT_AVERAGE_SCORE",
                passed=(
                    recent_average
                    >= self.thresholds.min_recent_average_score
                ),
                title="Média recente do score",
                pass_message=(
                    "A média recente atende ao mínimo."
                ),
                fail_message=(
                    "A média recente ainda está abaixo do mínimo."
                ),
                current_value=recent_average,
                expected_value=self.thresholds.min_recent_average_score,
                category="qualification",
            ),
            self._check(
                code="RECENT_WARNING_LIMIT",
                passed=(
                    recent_warning
                    <= self.thresholds.max_recent_warning
                ),
                title="Warnings recentes",
                pass_message=(
                    "A quantidade de WARNING está dentro do limite."
                ),
                fail_message=(
                    "Há WARNING recentes além do limite."
                ),
                current_value=recent_warning,
                expected_value=self.thresholds.max_recent_warning,
                category="qualification",
            ),
            self._check(
                code="RECENT_BLOCKED_LIMIT",
                passed=(
                    recent_blocked
                    <= self.thresholds.max_recent_blocked
                ),
                title="Bloqueios recentes",
                pass_message=(
                    "Não há estados BLOCKED além do limite."
                ),
                fail_message=(
                    "Há estados BLOCKED recentes além do limite."
                ),
                current_value=recent_blocked,
                expected_value=self.thresholds.max_recent_blocked,
                category="qualification",
            ),
            self._check(
                code="RECENT_CRITICAL_LIMIT",
                passed=(
                    recent_critical
                    <= self.thresholds.max_recent_critical
                ),
                title="Críticos recentes",
                pass_message=(
                    "Não há estados CRITICAL além do limite."
                ),
                fail_message=(
                    "Há estados CRITICAL recentes além do limite."
                ),
                current_value=recent_critical,
                expected_value=self.thresholds.max_recent_critical,
                category="qualification",
            ),
            self._check(
                code="PAPER_ONLY_SCOPE",
                passed=True,
                title="Escopo da qualificação",
                pass_message=(
                    "A qualificação é restrita ao ambiente Paper."
                ),
                fail_message=(
                    "A qualificação não pode autorizar execução live."
                ),
                current_value="PAPER_ASSURANCE_ONLY",
                expected_value="PAPER_ASSURANCE_ONLY",
                category="safety",
            ),
        ]

        checks = (
            data_checks
            + qualification_checks
        )

        failed_data = [
            item
            for item in data_checks
            if item.status == "FAIL"
        ]

        failed_qualification = [
            item
            for item in qualification_checks
            if item.status == "FAIL"
        ]

        if failed_data:
            status = "INSUFFICIENT_DATA"

        elif failed_qualification:
            status = "NOT_QUALIFIED"

        else:
            status = "QUALIFIED"

        passed_checks = sum(
            1
            for item in checks
            if item.status == "PASS"
        )

        qualification_score = round(
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
            qualification_score = min(
                qualification_score,
                69.0,
            )

        elif status == "NOT_QUALIFIED":
            qualification_score = min(
                qualification_score,
                79.0,
            )

        return {
            "status": status,
            "qualified": (
                status == "QUALIFIED"
            ),
            "scope": "PAPER_ASSURANCE_ONLY",
            "generated_at": _utc_now(),
            "qualification_score": qualification_score,
            "thresholds": asdict(
                self.thresholds
            ),
            "summary": {
                "total_checks": len(checks),
                "passed_checks": passed_checks,
                "failed_checks": (
                    len(checks)
                    - passed_checks
                ),
                "failed_data_checks": len(
                    failed_data
                ),
                "failed_qualification_checks": len(
                    failed_qualification
                ),
                "total_history_entries": total_entries,
                "recent_entries": len(entries),
                "latest_status": latest_status,
                "latest_score": latest_score,
                "recent_average_score": recent_average,
                "assured_streak": assured_streak,
                "recent_warning": recent_warning,
                "recent_blocked": recent_blocked,
                "recent_critical": recent_critical,
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
            "manual_start_required": True,
            **self._safe_flags(),
        }


paper_assurance_qualification_gate = (
    PaperAssuranceQualificationGate()
)
