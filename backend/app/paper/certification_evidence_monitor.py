from __future__ import annotations

import os
from collections import Counter
from collections.abc import Callable
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.certification_evidence import (
    PaperCertificationEvidence,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now(
    now_provider: Callable[
        [],
        datetime,
    ],
) -> str:
    value = now_provider()

    if value.tzinfo is None:
        value = value.replace(
            tzinfo=timezone.utc
        )

    return value.astimezone(
        timezone.utc
    ).isoformat()


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


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            str(value).replace(
                "Z",
                "+00:00",
            )
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


@dataclass(frozen=True)
class EvidenceMonitorAlert:
    code: str
    severity: str
    title: str
    message: str
    current_value: Any = None
    threshold: Any = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class PaperCertificationEvidenceMonitor:
    """Monitor somente leitura da cadeia de evidências Paper."""

    def __init__(
        self,
        *,
        evidence_factory: Callable[
            [],
            PaperCertificationEvidence,
        ] = PaperCertificationEvidence,
        stale_hours: float | None = None,
        min_entries: int | None = None,
        now_provider: Callable[
            [],
            datetime,
        ] = _utc_now,
    ) -> None:
        self.evidence_factory = (
            evidence_factory
        )

        self.stale_hours = max(
            1.0,
            (
                _env_float(
                    "PAPER_EVIDENCE_MONITOR_STALE_HOURS",
                    72.0,
                )
                if stale_hours is None
                else float(stale_hours)
            ),
        )

        self.min_entries = max(
            1,
            (
                _env_int(
                    "PAPER_EVIDENCE_MONITOR_MIN_ENTRIES",
                    1,
                )
                if min_entries is None
                else int(min_entries)
            ),
        )

        self.now_provider = now_provider

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
                    f"{name}: {field} "
                    "não está explicitamente bloqueado."
                )

        if payload.get(
            "read_only"
        ) is not True:
            raise RuntimeError(
                f"{name}: conteúdo não está "
                "marcado como somente leitura."
            )

    def _latest_age_hours(
        self,
        latest: Mapping[str, Any] | None,
    ) -> float | None:
        if latest is None:
            return None

        captured_at = _parse_datetime(
            latest.get("captured_at")
        )

        if captured_at is None:
            return None

        now = self.now_provider()

        if now.tzinfo is None:
            now = now.replace(
                tzinfo=timezone.utc
            )

        delta = (
            now.astimezone(timezone.utc)
            - captured_at
        )

        return max(
            0.0,
            round(
                delta.total_seconds()
                / 3600.0,
                6,
            ),
        )

    @staticmethod
    def _score(
        alerts: list[
            EvidenceMonitorAlert
        ],
        *,
        no_data: bool,
    ) -> int:
        if no_data:
            return 0

        score = 100

        for alert in alerts:
            if alert.severity == "critical":
                score -= 40

            elif alert.severity == "warning":
                score -= 15

            elif alert.severity == "info":
                score -= 5

        score = max(
            0,
            min(100, score),
        )

        if any(
            item.severity == "critical"
            for item in alerts
        ):
            score = min(score, 49)

        elif any(
            item.severity == "warning"
            for item in alerts
        ):
            score = min(score, 79)

        return score

    def snapshot(
        self,
    ) -> dict[str, Any]:
        evidence = self.evidence_factory()

        summary = evidence.summary()
        verification = evidence.verify()
        latest = evidence.latest()

        self._validate_safe_payload(
            "summary",
            summary,
        )

        self._validate_safe_payload(
            "verification",
            verification,
        )

        if latest is not None:
            self._validate_safe_payload(
                "latest",
                latest,
            )

        alerts: list[
            EvidenceMonitorAlert
        ] = []

        total_entries = _integer(
            summary.get("total_entries")
        )

        no_data = total_entries == 0

        if no_data:
            alerts.append(
                EvidenceMonitorAlert(
                    code="NO_EVIDENCE_DATA",
                    severity="info",
                    title=(
                        "Nenhuma evidência registrada"
                    ),
                    message=(
                        "O arquivo ainda não possui "
                        "evidências de certificação."
                    ),
                    current_value=0,
                    threshold=self.min_entries,
                )
            )

        elif total_entries < self.min_entries:
            alerts.append(
                EvidenceMonitorAlert(
                    code="EVIDENCE_COUNT_LOW",
                    severity="warning",
                    title=(
                        "Poucas evidências registradas"
                    ),
                    message=(
                        "A quantidade de evidências está "
                        "abaixo do mínimo operacional."
                    ),
                    current_value=total_entries,
                    threshold=self.min_entries,
                )
            )

        chain_status = str(
            verification.get("status")
            or "UNKNOWN"
        ).upper()

        chain_valid = (
            verification.get("valid")
            is True
        )

        if (
            not no_data
            and (
                not chain_valid
                or chain_status == "BROKEN"
            )
        ):
            alerts.append(
                EvidenceMonitorAlert(
                    code="EVIDENCE_CHAIN_BROKEN",
                    severity="critical",
                    title=(
                        "Integridade da cadeia comprometida"
                    ),
                    message=(
                        "A verificação detectou alteração, "
                        "hash inválido ou chain head divergente."
                    ),
                    current_value=chain_status,
                    threshold="VALID",
                )
            )

        if latest is not None:
            if (
                latest.get("scope")
                != "PAPER_ONLY"
            ):
                alerts.append(
                    EvidenceMonitorAlert(
                        code="INVALID_EVIDENCE_SCOPE",
                        severity="critical",
                        title=(
                            "Escopo da evidência inválido"
                        ),
                        message=(
                            "A evidência mais recente não "
                            "está limitada a PAPER_ONLY."
                        ),
                        current_value=latest.get(
                            "scope"
                        ),
                        threshold="PAPER_ONLY",
                    )
                )

            latest_status = str(
                latest.get("status")
                or "UNKNOWN"
            ).upper()

            if latest_status == "BLOCKED":
                alerts.append(
                    EvidenceMonitorAlert(
                        code=(
                            "LATEST_CERTIFICATION_BLOCKED"
                        ),
                        severity="warning",
                        title=(
                            "Certificação mais recente bloqueada"
                        ),
                        message=(
                            "A evidência mais recente registra "
                            "uma certificação BLOCKED."
                        ),
                        current_value=latest_status,
                        threshold="CERTIFIED",
                    )
                )

            elif latest_status in {
                "PENDING",
                "NO_DATA",
            }:
                alerts.append(
                    EvidenceMonitorAlert(
                        code=(
                            "LATEST_CERTIFICATION_NOT_FINAL"
                        ),
                        severity="info",
                        title=(
                            "Certificação ainda não concluída"
                        ),
                        message=(
                            "A evidência mais recente ainda não "
                            "registra estado CERTIFIED."
                        ),
                        current_value=latest_status,
                        threshold="CERTIFIED",
                    )
                )

            age_hours = (
                self._latest_age_hours(
                    latest
                )
            )

            if age_hours is None:
                alerts.append(
                    EvidenceMonitorAlert(
                        code=(
                            "LATEST_EVIDENCE_DATE_INVALID"
                        ),
                        severity="warning",
                        title=(
                            "Data da evidência inválida"
                        ),
                        message=(
                            "Não foi possível calcular a idade "
                            "da evidência mais recente."
                        ),
                        current_value=latest.get(
                            "captured_at"
                        ),
                        threshold=(
                            f"até {self.stale_hours} horas"
                        ),
                    )
                )

            elif age_hours > self.stale_hours:
                alerts.append(
                    EvidenceMonitorAlert(
                        code="EVIDENCE_STALE",
                        severity="warning",
                        title=(
                            "Evidência desatualizada"
                        ),
                        message=(
                            "A evidência mais recente ultrapassou "
                            "o limite de idade configurado."
                        ),
                        current_value=age_hours,
                        threshold=self.stale_hours,
                    )
                )

        if no_data:
            status = "NO_DATA"

        elif any(
            item.severity == "critical"
            for item in alerts
        ):
            status = "CRITICAL"

        elif any(
            item.severity == "warning"
            for item in alerts
        ):
            status = "WARNING"

        else:
            status = "HEALTHY"

        counts = Counter(
            item.severity
            for item in alerts
        )

        score = self._score(
            alerts,
            no_data=no_data,
        )

        return {
            "status": status,
            "score": score,
            "generated_at": _iso_now(
                self.now_provider
            ),
            "alert_counts": {
                "critical": counts.get(
                    "critical",
                    0,
                ),
                "warning": counts.get(
                    "warning",
                    0,
                ),
                "info": counts.get(
                    "info",
                    0,
                ),
            },
            "alerts": [
                item.to_dict()
                for item in alerts
            ],
            "diagnostics": {
                "total_entries": total_entries,
                "chain_status": chain_status,
                "chain_valid": chain_valid,
                "latest_status": (
                    latest.get("status")
                    if latest
                    else None
                ),
                "latest_score": (
                    latest.get(
                        "certification_score"
                    )
                    if latest
                    else None
                ),
                "latest_age_hours": (
                    self._latest_age_hours(
                        latest
                    )
                ),
                "chain_head": summary.get(
                    "chain_head"
                ),
            },
            "thresholds": {
                "min_entries": self.min_entries,
                "stale_hours": self.stale_hours,
            },
            **self._safe_flags(),
        }


paper_certification_evidence_monitor = (
    PaperCertificationEvidenceMonitor()
)
