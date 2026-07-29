from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.readiness_history import (
    PaperReadinessHistory,
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
class CertificationThresholds:
    min_evaluations: int
    min_consecutive_ready: int
    recent_window: int
    min_latest_score: float
    min_recent_average_score: float
    max_recent_not_ready: int

    @classmethod
    def from_env(
        cls,
    ) -> "CertificationThresholds":
        min_evaluations = max(
            1,
            _env_int(
                "PAPER_CERTIFICATION_MIN_EVALUATIONS",
                5,
            ),
        )

        min_consecutive_ready = max(
            1,
            _env_int(
                "PAPER_CERTIFICATION_MIN_CONSECUTIVE_READY",
                3,
            ),
        )

        recent_window = max(
            min_consecutive_ready,
            _env_int(
                "PAPER_CERTIFICATION_RECENT_WINDOW",
                5,
            ),
        )

        return cls(
            min_evaluations=min_evaluations,
            min_consecutive_ready=min_consecutive_ready,
            recent_window=recent_window,
            min_latest_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_CERTIFICATION_MIN_LATEST_SCORE",
                        80.0,
                    ),
                ),
            ),
            min_recent_average_score=max(
                0.0,
                min(
                    100.0,
                    _env_float(
                        "PAPER_CERTIFICATION_MIN_RECENT_AVERAGE_SCORE",
                        80.0,
                    ),
                ),
            ),
            max_recent_not_ready=max(
                0,
                _env_int(
                    "PAPER_CERTIFICATION_MAX_RECENT_NOT_READY",
                    0,
                ),
            ),
        )


@dataclass(frozen=True)
class CertificationCheck:
    code: str
    status: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class PaperStabilityCertification:
    """Certificação de estabilidade limitada ao ambiente Paper."""

    def __init__(
        self,
        *,
        history: PaperReadinessHistory | None = None,
        thresholds: CertificationThresholds | None = None,
    ) -> None:
        self.history = (
            history
            if history is not None
            else PaperReadinessHistory()
        )

        self.thresholds = (
            thresholds
            if thresholds is not None
            else CertificationThresholds.from_env()
        )

    @staticmethod
    def _validate_safe_payload(
        name: str,
        payload: Mapping[str, Any],
    ) -> None:
        if payload.get("execution_authorized") is not False:
            raise RuntimeError(
                f"{name}: execução não está bloqueada."
            )

        if payload.get("live_execution") is not False:
            raise RuntimeError(
                f"{name}: execução live não está bloqueada."
            )

        if payload.get("financial_execution") is not False:
            raise RuntimeError(
                f"{name}: execução financeira não está bloqueada."
            )

        if payload.get("read_only") is not True:
            raise RuntimeError(
                f"{name}: conteúdo não está marcado como somente leitura."
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
        fail_status: str,
    ) -> CertificationCheck:
        return CertificationCheck(
            code=code,
            status=(
                "PASS"
                if passed
                else fail_status
            ),
            title=title,
            message=(
                pass_message
                if passed
                else fail_message
            ),
            current_value=current_value,
            expected_value=expected_value,
        )

    @staticmethod
    def _consecutive_ready(
        entries: list[Mapping[str, Any]],
    ) -> int:
        count = 0

        for entry in entries:
            if str(
                entry.get("status") or ""
            ).upper() == "READY":
                count += 1
            else:
                break

        return count

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
                latest.get("readiness_score")
            )
            if latest
            else 0.0
        )

        recent_scores = [
            _number(
                item.get("readiness_score")
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

        consecutive_ready = (
            self._consecutive_ready(
                entries
            )
        )

        recent_not_ready = sum(
            1
            for item in entries
            if str(
                item.get("status") or ""
            ).upper() == "NOT_READY"
        )

        latest_is_ready = (
            latest_status == "READY"
        )

        checks = [
            self._check(
                code="MIN_EVALUATIONS",
                passed=(
                    total_entries
                    >= self.thresholds.min_evaluations
                ),
                title="Quantidade de avaliações",
                pass_message=(
                    "O histórico possui avaliações suficientes."
                ),
                fail_message=(
                    "O histórico ainda não possui avaliações suficientes."
                ),
                current_value=total_entries,
                expected_value=self.thresholds.min_evaluations,
                fail_status="PENDING",
            ),
            self._check(
                code="LATEST_STATUS_READY",
                passed=latest_is_ready,
                title="Último status",
                pass_message=(
                    "A avaliação mais recente está READY."
                ),
                fail_message=(
                    "A avaliação mais recente ainda não está READY."
                ),
                current_value=latest_status,
                expected_value="READY",
                fail_status=(
                    "BLOCKER"
                    if latest_status == "NOT_READY"
                    else "PENDING"
                ),
            ),
            self._check(
                code="CONSECUTIVE_READY",
                passed=(
                    consecutive_ready
                    >= self.thresholds.min_consecutive_ready
                ),
                title="Sequência consecutiva de READY",
                pass_message=(
                    "A sequência mínima de READY foi alcançada."
                ),
                fail_message=(
                    "A sequência consecutiva de READY ainda é insuficiente."
                ),
                current_value=consecutive_ready,
                expected_value=(
                    self.thresholds.min_consecutive_ready
                ),
                fail_status="PENDING",
            ),
            self._check(
                code="LATEST_SCORE",
                passed=(
                    latest_score
                    >= self.thresholds.min_latest_score
                ),
                title="Score da avaliação mais recente",
                pass_message=(
                    "O score mais recente atende ao mínimo."
                ),
                fail_message=(
                    "O score mais recente está abaixo do mínimo."
                ),
                current_value=latest_score,
                expected_value=(
                    self.thresholds.min_latest_score
                ),
                fail_status="PENDING",
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
                expected_value=(
                    self.thresholds.min_recent_average_score
                ),
                fail_status="PENDING",
            ),
            self._check(
                code="RECENT_NOT_READY_LIMIT",
                passed=(
                    recent_not_ready
                    <= self.thresholds.max_recent_not_ready
                ),
                title="Regressões recentes",
                pass_message=(
                    "Não há regressões além do limite definido."
                ),
                fail_message=(
                    "Há avaliações NOT_READY além do limite recente."
                ),
                current_value=recent_not_ready,
                expected_value=(
                    self.thresholds.max_recent_not_ready
                ),
                fail_status="BLOCKER",
            ),
            self._check(
                code="LIVE_EXECUTION_REMAINS_BLOCKED",
                passed=True,
                title="Escopo da certificação",
                pass_message=(
                    "A certificação é exclusiva para Paper e não autoriza live."
                ),
                fail_message=(
                    "A certificação não pode autorizar execução live."
                ),
                current_value="PAPER_ONLY",
                expected_value="PAPER_ONLY",
                fail_status="BLOCKER",
            ),
        ]

        blockers = [
            item
            for item in checks
            if item.status == "BLOCKER"
        ]

        pending = [
            item
            for item in checks
            if item.status == "PENDING"
        ]

        passed = [
            item
            for item in checks
            if item.status == "PASS"
        ]

        if total_entries == 0:
            status = "NO_DATA"

        elif blockers:
            status = "BLOCKED"

        elif pending:
            status = "PENDING"

        else:
            status = "CERTIFIED"

        total_checks = len(checks)

        score = round(
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
            "certified": status == "CERTIFIED",
            "scope": "PAPER_ONLY",
            "generated_at": _utc_now(),
            "certification_score": score,
            "thresholds": asdict(
                self.thresholds
            ),
            "summary": {
                "total_checks": total_checks,
                "passed_checks": len(passed),
                "pending_checks": len(pending),
                "blockers": len(blockers),
                "total_history_entries": total_entries,
                "latest_status": latest_status,
                "latest_score": latest_score,
                "recent_average_score": recent_average,
                "consecutive_ready": consecutive_ready,
                "recent_not_ready": recent_not_ready,
            },
            "checks": [
                item.to_dict()
                for item in checks
            ],
            "blockers": [
                item.to_dict()
                for item in blockers
            ],
            "pending": [
                item.to_dict()
                for item in pending
            ],
            "paper_execution_authorized": False,
            "live_authorization": False,
            "manual_start_required": True,
            "read_only": True,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
        }


paper_stability_certification = (
    PaperStabilityCertification()
)
