from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.certification_evidence import (
    PaperCertificationEvidence,
)
from app.paper.certification_evidence_incident_runtime import (
    paper_evidence_incident_runtime,
)
from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)
from app.paper.certification_evidence_monitor import (
    paper_certification_evidence_monitor,
)
from app.paper.stability_certification import (
    paper_stability_certification,
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


class PaperCertificationAssuranceCenter:
    """Visão consolidada e somente leitura da certificação Paper."""

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
    def _validate_component(
        name: str,
        payload: Mapping[str, Any],
        *,
        require_read_only: bool = True,
    ) -> None:
        required_false = (
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
                    f"{name}: {field} "
                    "não está explicitamente bloqueado."
                )

        if (
            require_read_only
            and payload.get(
                "read_only"
            )
            is not True
        ):
            raise RuntimeError(
                f"{name}: payload não está "
                "marcado como somente leitura."
            )

    @staticmethod
    def _global_status(
        *,
        certification_status: str,
        monitor_status: str,
        chain_valid: bool,
        active_critical: int,
        active_warning: int,
        runtime_failures: int,
    ) -> str:
        if (
            not chain_valid
            or monitor_status == "CRITICAL"
            or active_critical > 0
        ):
            return "CRITICAL"

        if certification_status == "BLOCKED":
            return "BLOCKED"

        if certification_status in {
            "PENDING",
            "NO_DATA",
        } or monitor_status == "NO_DATA":
            return "PENDING"

        if (
            monitor_status == "WARNING"
            or active_warning > 0
            or runtime_failures > 0
        ):
            return "WARNING"

        if (
            certification_status
            == "CERTIFIED"
            and monitor_status
            == "HEALTHY"
            and chain_valid
        ):
            return "ASSURED"

        return "UNKNOWN"

    def snapshot(
        self,
    ) -> dict[str, Any]:
        certification = (
            paper_stability_certification
            .evaluate()
        )

        evidence = (
            PaperCertificationEvidence()
        )

        evidence_summary = (
            evidence.summary()
        )

        verification = (
            evidence.verify()
        )

        monitor = (
            paper_certification_evidence_monitor
            .snapshot()
        )

        incidents = (
            PaperCertificationEvidenceIncidentJournal()
            .summary()
        )

        runtime = (
            paper_evidence_incident_runtime
            .status()
        )

        self._validate_component(
            "certification",
            certification,
        )

        self._validate_component(
            "evidence_summary",
            evidence_summary,
        )

        self._validate_component(
            "verification",
            verification,
        )

        self._validate_component(
            "monitor",
            monitor,
        )

        self._validate_component(
            "incidents",
            incidents,
        )

        self._validate_component(
            "runtime",
            runtime,
            require_read_only=False,
        )

        certification_status = str(
            certification.get(
                "status"
            )
            or "UNKNOWN"
        ).upper()

        monitor_status = str(
            monitor.get("status")
            or "UNKNOWN"
        ).upper()

        chain_valid = (
            verification.get("valid")
            is True
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

        runtime_failures = _integer(
            runtime.get(
                "failed_cycles"
            )
        )

        global_status = (
            self._global_status(
                certification_status=(
                    certification_status
                ),
                monitor_status=(
                    monitor_status
                ),
                chain_valid=chain_valid,
                active_critical=(
                    active_critical
                ),
                active_warning=(
                    active_warning
                ),
                runtime_failures=(
                    runtime_failures
                ),
            )
        )

        assurance_score = min(
            _number(
                certification.get(
                    "certification_score"
                )
            ),
            _number(
                monitor.get("score")
            ),
        )

        if global_status == "CRITICAL":
            assurance_score = min(
                assurance_score,
                49.0,
            )

        elif global_status in {
            "BLOCKED",
            "WARNING",
        }:
            assurance_score = min(
                assurance_score,
                79.0,
            )

        elif global_status == "PENDING":
            assurance_score = min(
                assurance_score,
                69.0,
            )

        return {
            "status": global_status,
            "assured": (
                global_status
                == "ASSURED"
            ),
            "scope": "PAPER_ONLY",
            "generated_at": _utc_now(),
            "assurance_score": round(
                assurance_score,
                2,
            ),
            "summary": {
                "certification_status": (
                    certification_status
                ),
                "certification_score": (
                    certification.get(
                        "certification_score"
                    )
                ),
                "monitor_status": (
                    monitor_status
                ),
                "monitor_score": (
                    monitor.get("score")
                ),
                "chain_status": (
                    verification.get(
                        "status"
                    )
                ),
                "chain_valid": (
                    chain_valid
                ),
                "evidence_entries": (
                    evidence_summary.get(
                        "total_entries"
                    )
                ),
                "active_incidents": (
                    incidents.get(
                        "active_incidents"
                    )
                ),
                "active_critical": (
                    active_critical
                ),
                "active_warning": (
                    active_warning
                ),
                "runtime_status": (
                    runtime.get("status")
                ),
                "runtime_cycles": (
                    runtime.get(
                        "total_cycles"
                    )
                ),
                "runtime_failures": (
                    runtime_failures
                ),
            },
            "certification": certification,
            "evidence": {
                "summary": evidence_summary,
                "verification": (
                    verification
                ),
            },
            "monitor": monitor,
            "incidents": incidents,
            "runtime": runtime,
            "manual_start_required": True,
            **self._safe_flags(),
        }


paper_certification_assurance_center = (
    PaperCertificationAssuranceCenter()
)
