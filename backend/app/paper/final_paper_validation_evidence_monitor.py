from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.final_paper_validation_evidence import (
    FinalPaperValidationEvidence,
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


def _parse_datetime(value: Any) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)

    return parsed.astimezone(timezone.utc)


@dataclass(frozen=True)
class EvidenceMonitorThresholds:
    stale_hours: float
    min_entries: int

    @classmethod
    def from_env(cls) -> "EvidenceMonitorThresholds":
        return cls(
            stale_hours=max(
                1.0,
                _env_float(
                    "PAPER_FINAL_EVIDENCE_MONITOR_STALE_HOURS",
                    72.0,
                ),
            ),
            min_entries=max(
                1,
                _env_int(
                    "PAPER_FINAL_EVIDENCE_MONITOR_MIN_ENTRIES",
                    1,
                ),
            ),
        )


@dataclass(frozen=True)
class EvidenceMonitorAlert:
    code: str
    severity: str
    title: str
    message: str
    current_value: Any = None
    expected_value: Any = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class FinalPaperValidationEvidenceMonitor:
    """Monitor somente leitura da integridade das evidências finais."""

    def __init__(
        self,
        *,
        evidence: FinalPaperValidationEvidence | None = None,
        thresholds: EvidenceMonitorThresholds | None = None,
        now_provider=None,
    ) -> None:
        self.evidence = (
            evidence
            if evidence is not None
            else FinalPaperValidationEvidence()
        )
        self.thresholds = (
            thresholds
            if thresholds is not None
            else EvidenceMonitorThresholds.from_env()
        )
        self.now_provider = now_provider or (
            lambda: datetime.now(timezone.utc)
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

        if payload.get("read_only") is not True:
            raise RuntimeError(
                f"{name}: payload não está marcado como somente leitura."
            )

    @staticmethod
    def _alert(
        *,
        code: str,
        severity: str,
        title: str,
        message: str,
        current_value: Any = None,
        expected_value: Any = None,
    ) -> EvidenceMonitorAlert:
        return EvidenceMonitorAlert(
            code=code,
            severity=severity,
            title=title,
            message=message,
            current_value=current_value,
            expected_value=expected_value,
        )

    def evaluate(self) -> dict[str, Any]:
        summary = self.evidence.summary()
        integrity = self.evidence.verify()
        latest = self.evidence.latest()

        self._validate_safe_payload("evidence_summary", summary)
        self._validate_safe_payload("evidence_integrity", integrity)

        if latest is not None:
            self._validate_safe_payload("latest_evidence", latest)

        total_entries = int(summary.get("total_entries") or 0)
        alerts: list[EvidenceMonitorAlert] = []

        if total_entries < self.thresholds.min_entries:
            alerts.append(
                self._alert(
                    code="NO_EVIDENCE",
                    severity="info",
                    title="Arquivo probatório sem evidências suficientes",
                    message=(
                        "Ainda não existem evidências suficientes "
                        "para avaliar a estabilidade do arquivo."
                    ),
                    current_value=total_entries,
                    expected_value=self.thresholds.min_entries,
                )
            )

        integrity_status = str(
            integrity.get("integrity_status") or "BROKEN"
        ).upper()

        if integrity_status == "BROKEN" or integrity.get("valid") is not True:
            alerts.append(
                self._alert(
                    code="CHAIN_BROKEN",
                    severity="critical",
                    title="Cadeia de evidências corrompida",
                    message=(
                        "A verificação SHA-256 detectou uma quebra "
                        "na cadeia de evidências."
                    ),
                    current_value=integrity.get("reason"),
                    expected_value="VALID",
                )
            )

        chain_head = summary.get("chain_head")

        if total_entries > 0 and not chain_head:
            alerts.append(
                self._alert(
                    code="CHAIN_HEAD_MISSING",
                    severity="critical",
                    title="Chain head ausente",
                    message=(
                        "Existem evidências, mas o hash final "
                        "da cadeia não está disponível."
                    ),
                    current_value=chain_head,
                    expected_value="SHA-256 válido",
                )
            )

        if latest is not None:
            scope = latest.get("scope")

            if scope != "PAPER_VALIDATION_ONLY":
                alerts.append(
                    self._alert(
                        code="INVALID_SCOPE",
                        severity="critical",
                        title="Escopo da evidência inválido",
                        message=(
                            "A evidência mais recente não está "
                            "restrita ao ambiente Paper."
                        ),
                        current_value=scope,
                        expected_value="PAPER_VALIDATION_ONLY",
                    )
                )

            latest_status = str(
                latest.get("status") or "UNKNOWN"
            ).upper()

            if latest_status == "PAPER_BLOCKED":
                alerts.append(
                    self._alert(
                        code="LATEST_VALIDATION_BLOCKED",
                        severity="critical",
                        title="Validação final bloqueada",
                        message=(
                            "A evidência mais recente registra "
                            "PAPER_BLOCKED."
                        ),
                        current_value=latest_status,
                        expected_value="PAPER_VALIDATED",
                    )
                )

            elif latest_status in {
                "PAPER_PENDING",
                "INSUFFICIENT_DATA",
            }:
                alerts.append(
                    self._alert(
                        code="LATEST_VALIDATION_NOT_FINAL",
                        severity="warning",
                        title="Validação final ainda não consolidada",
                        message=(
                            "A evidência mais recente ainda não "
                            "registra PAPER_VALIDATED."
                        ),
                        current_value=latest_status,
                        expected_value="PAPER_VALIDATED",
                    )
                )

            captured_at = _parse_datetime(
                latest.get("captured_at")
            )

            if captured_at is None:
                alerts.append(
                    self._alert(
                        code="INVALID_CAPTURE_TIME",
                        severity="warning",
                        title="Data da evidência inválida",
                        message=(
                            "A data da evidência mais recente "
                            "não pôde ser interpretada."
                        ),
                        current_value=latest.get("captured_at"),
                        expected_value="ISO-8601",
                    )
                )
            else:
                now = self.now_provider()

                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)

                age_hours = max(
                    0.0,
                    (
                        now.astimezone(timezone.utc)
                        - captured_at
                    ).total_seconds()
                    / 3600.0,
                )

                if age_hours > self.thresholds.stale_hours:
                    alerts.append(
                        self._alert(
                            code="STALE_EVIDENCE",
                            severity="warning",
                            title="Evidência final desatualizada",
                            message=(
                                "A evidência mais recente excedeu "
                                "o limite de atualização."
                            ),
                            current_value=round(age_hours, 3),
                            expected_value=(
                                self.thresholds.stale_hours
                            ),
                        )
                    )

        critical_count = sum(
            1
            for alert in alerts
            if alert.severity == "critical"
        )
        warning_count = sum(
            1
            for alert in alerts
            if alert.severity == "warning"
        )
        info_count = sum(
            1
            for alert in alerts
            if alert.severity == "info"
        )

        score = max(
            0,
            100
            - critical_count * 40
            - warning_count * 15
            - info_count * 5,
        )

        if critical_count:
            status = "CRITICAL"
            score = min(score, 49)

        elif total_entries < self.thresholds.min_entries:
            status = "NO_DATA"
            score = 0

        elif warning_count:
            status = "WARNING"
            score = min(score, 79)

        else:
            status = "HEALTHY"

        return {
            "status": status,
            "score": score,
            "generated_at": _utc_now(),
            "summary": {
                "total_entries": total_entries,
                "integrity_status": integrity_status,
                "integrity_valid": integrity.get("valid") is True,
                "chain_head": chain_head,
                "latest_status": (
                    latest.get("status")
                    if latest
                    else None
                ),
                "latest_captured_at": (
                    latest.get("captured_at")
                    if latest
                    else None
                ),
                "critical_alerts": critical_count,
                "warning_alerts": warning_count,
                "info_alerts": info_count,
                "total_alerts": len(alerts),
            },
            "thresholds": asdict(self.thresholds),
            "alerts": [
                alert.to_dict()
                for alert in alerts
            ],
            "components": {
                "evidence_summary": summary,
                "integrity": integrity,
                "latest": latest,
            },
            **self._safe_flags(),
        }


final_paper_validation_evidence_monitor = (
    FinalPaperValidationEvidenceMonitor()
)
