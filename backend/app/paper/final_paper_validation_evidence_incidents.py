from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

from app.paper.final_paper_validation_evidence_monitor import (
    FinalPaperValidationEvidenceMonitor,
)


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )


def _incident_id(alert: Mapping[str, Any]) -> str:
    identity = {
        "code": str(alert.get("code") or "UNKNOWN"),
        "severity": str(alert.get("severity") or "unknown").lower(),
        "title": str(alert.get("title") or "Sem título"),
    }

    digest = hashlib.sha256(
        _canonical_json(identity).encode("utf-8")
    ).hexdigest()[:24]

    return f"fpe-{digest}"


class FinalPaperEvidenceIncidentJournal:
    """Diário persistente dos alertas do monitor de evidências finais."""

    VALID_INCIDENT_STATUSES = {"ACTIVE", "RESOLVED"}
    VALID_SEVERITIES = {"critical", "warning", "info"}

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        monitor: FinalPaperValidationEvidenceMonitor | None = None,
        max_snapshots: int = 5000,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "PAPER_FINAL_EVIDENCE_INCIDENTS_PATH",
                "paper_data/final_paper_validation_evidence_incidents.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.monitor = (
            monitor
            if monitor is not None
            else FinalPaperValidationEvidenceMonitor()
        )
        self.max_snapshots = max(10, min(int(max_snapshots), 50000))
        self._lock = threading.RLock()

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
    def _empty_state(cls) -> dict[str, Any]:
        return {
            "version": 1,
            "created_at": None,
            "updated_at": None,
            "incidents": [],
            "snapshots": [],
            **cls._safe_flags(),
        }

    @classmethod
    def _validate_safety(
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

    @classmethod
    def _validate_incident(
        cls,
        incident: Mapping[str, Any],
    ) -> None:
        status = str(incident.get("status") or "").upper()

        if status not in cls.VALID_INCIDENT_STATUSES:
            raise ValueError("Status de incidente inválido.")

        severity = str(incident.get("severity") or "").lower()

        if severity not in cls.VALID_SEVERITIES:
            raise ValueError("Severidade de incidente inválida.")

        if not incident.get("id"):
            raise ValueError("Identificador do incidente ausente.")

        cls._validate_safety("incident", incident)

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return self._empty_state()

            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            if not isinstance(payload, dict):
                raise ValueError(
                    "Arquivo do diário de incidentes inválido."
                )

            payload.setdefault("version", 1)
            payload.setdefault("created_at", None)
            payload.setdefault("updated_at", None)
            payload.setdefault("incidents", [])
            payload.setdefault("snapshots", [])

            if not isinstance(payload["incidents"], list):
                raise ValueError("Lista de incidentes inválida.")

            if not isinstance(payload["snapshots"], list):
                raise ValueError("Lista de snapshots inválida.")

            self._validate_safety("incident_state", payload)

            for incident in payload["incidents"]:
                if not isinstance(incident, Mapping):
                    raise ValueError("Entrada de incidente inválida.")

                self._validate_incident(incident)

            for snapshot in payload["snapshots"]:
                if not isinstance(snapshot, Mapping):
                    raise ValueError("Snapshot do monitor inválido.")

                self._validate_safety("monitor_snapshot", snapshot)

            return payload

    def _save(self, state: Mapping[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)

        payload = deepcopy(dict(state))
        payload.update(self._safe_flags())

        handle, temp_name = tempfile.mkstemp(
            prefix=f"{self.path.stem}_",
            suffix=".tmp",
            dir=str(self.path.parent),
        )

        temp_path = Path(temp_name)

        try:
            with os.fdopen(handle, "w", encoding="utf-8") as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                    default=str,
                )
                file.flush()
                os.fsync(file.fileno())

            temp_path.replace(self.path)

        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _new_incident(
        cls,
        alert: Mapping[str, Any],
        *,
        incident_id: str,
        captured_at: str,
    ) -> dict[str, Any]:
        return {
            "id": incident_id,
            "code": str(alert.get("code") or "UNKNOWN"),
            "severity": str(alert.get("severity") or "info").lower(),
            "title": str(alert.get("title") or "Sem título"),
            "message": str(alert.get("message") or ""),
            "status": "ACTIVE",
            "first_seen_at": captured_at,
            "last_seen_at": captured_at,
            "resolved_at": None,
            "occurrences": 1,
            "reactivations": 0,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "current_value": deepcopy(alert.get("current_value")),
            "expected_value": deepcopy(alert.get("expected_value")),
            **cls._safe_flags(),
        }

    @classmethod
    def _monitor_snapshot(
        cls,
        monitor: Mapping[str, Any],
        *,
        captured_at: str,
    ) -> dict[str, Any]:
        summary = monitor.get("summary") or {}
        alerts = [
            item
            for item in (monitor.get("alerts") or [])
            if isinstance(item, Mapping)
        ]

        return {
            "captured_at": captured_at,
            "monitor_status": monitor.get("status"),
            "monitor_score": monitor.get("score"),
            "total_entries": summary.get("total_entries"),
            "integrity_status": summary.get("integrity_status"),
            "latest_status": summary.get("latest_status"),
            "critical_alerts": summary.get("critical_alerts"),
            "warning_alerts": summary.get("warning_alerts"),
            "info_alerts": summary.get("info_alerts"),
            "alert_codes": [
                str(item.get("code") or "UNKNOWN")
                for item in alerts
            ],
            **cls._safe_flags(),
        }

    def capture(self) -> dict[str, Any]:
        monitor_payload = self.monitor.evaluate()

        self._validate_safety("evidence_monitor", monitor_payload)

        alerts = [
            item
            for item in (monitor_payload.get("alerts") or [])
            if isinstance(item, Mapping)
        ]

        for alert in alerts:
            severity = str(alert.get("severity") or "").lower()

            if severity not in self.VALID_SEVERITIES:
                raise RuntimeError(
                    "O monitor retornou severidade inválida."
                )

        with self._lock:
            state = self.load()
            captured_at = _utc_now()

            incidents = [
                dict(item)
                for item in state.get("incidents", [])
                if isinstance(item, Mapping)
            ]

            by_id = {
                str(item.get("id")): item
                for item in incidents
            }

            current_ids: set[str] = set()
            created: list[str] = []
            updated: list[str] = []
            reactivated: list[str] = []
            resolved: list[str] = []

            for alert in alerts:
                incident_id = _incident_id(alert)
                current_ids.add(incident_id)
                existing = by_id.get(incident_id)

                if existing is None:
                    incident = self._new_incident(
                        alert,
                        incident_id=incident_id,
                        captured_at=captured_at,
                    )
                    incidents.append(incident)
                    by_id[incident_id] = incident
                    created.append(incident_id)
                    continue

                if existing.get("status") == "RESOLVED":
                    existing["status"] = "ACTIVE"
                    existing["resolved_at"] = None
                    existing["reactivations"] = int(
                        existing.get("reactivations") or 0
                    ) + 1
                    existing["acknowledged_at"] = None
                    existing["acknowledged_by"] = None
                    reactivated.append(incident_id)
                else:
                    updated.append(incident_id)

                existing["last_seen_at"] = captured_at
                existing["occurrences"] = int(
                    existing.get("occurrences") or 0
                ) + 1
                existing["severity"] = str(
                    alert.get("severity") or "info"
                ).lower()
                existing["title"] = str(
                    alert.get("title") or "Sem título"
                )
                existing["message"] = str(
                    alert.get("message") or ""
                )
                existing["current_value"] = deepcopy(
                    alert.get("current_value")
                )
                existing["expected_value"] = deepcopy(
                    alert.get("expected_value")
                )
                existing.update(self._safe_flags())

            for incident in incidents:
                incident_id = str(incident.get("id"))

                if (
                    incident.get("status") == "ACTIVE"
                    and incident_id not in current_ids
                ):
                    incident["status"] = "RESOLVED"
                    incident["resolved_at"] = captured_at
                    resolved.append(incident_id)
                    incident.update(self._safe_flags())

            snapshots = [
                dict(item)
                for item in state.get("snapshots", [])
                if isinstance(item, Mapping)
            ]

            snapshots.append(
                self._monitor_snapshot(
                    monitor_payload,
                    captured_at=captured_at,
                )
            )

            snapshots = snapshots[-self.max_snapshots :]

            state.update(
                {
                    "created_at": state.get("created_at") or captured_at,
                    "updated_at": captured_at,
                    "incidents": incidents,
                    "snapshots": snapshots,
                    **self._safe_flags(),
                }
            )

            self._save(state)

            return {
                "status": "captured",
                "captured_at": captured_at,
                "created": created,
                "updated": updated,
                "reactivated": reactivated,
                "resolved": resolved,
                "monitor": monitor_payload,
                "summary": self.summary(),
                **self._safe_flags(),
            }

    def acknowledge(
        self,
        incident_id: str,
        *,
        operator: str = "administrator",
    ) -> dict[str, Any]:
        normalized_id = str(incident_id).strip()

        if not normalized_id:
            raise ValueError("Identificador do incidente inválido.")

        normalized_operator = str(operator).strip() or "administrator"

        with self._lock:
            state = self.load()
            incidents = [
                dict(item)
                for item in state.get("incidents", [])
                if isinstance(item, Mapping)
            ]

            incident = next(
                (
                    item
                    for item in incidents
                    if item.get("id") == normalized_id
                ),
                None,
            )

            if incident is None:
                raise KeyError(normalized_id)

            acknowledged_at = _utc_now()
            incident["acknowledged_at"] = acknowledged_at
            incident["acknowledged_by"] = normalized_operator
            incident.update(self._safe_flags())

            state.update(
                {
                    "updated_at": acknowledged_at,
                    "incidents": incidents,
                    **self._safe_flags(),
                }
            )

            self._save(state)

            return {
                "status": "acknowledged",
                "incident": deepcopy(incident),
                "summary": self.summary(),
                **self._safe_flags(),
            }

    def get_incident(
        self,
        incident_id: str,
    ) -> dict[str, Any] | None:
        normalized_id = str(incident_id).strip()

        for incident in self.load().get("incidents", []):
            if incident.get("id") == normalized_id:
                return deepcopy(incident)

        return None

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 5000))
        normalized_status = str(status).upper() if status else None

        if (
            normalized_status is not None
            and normalized_status not in self.VALID_INCIDENT_STATUSES
        ):
            raise ValueError("Filtro de status de incidente inválido.")

        incidents = [
            deepcopy(item)
            for item in self.load().get("incidents", [])
            if isinstance(item, Mapping)
        ]

        if normalized_status:
            incidents = [
                item
                for item in incidents
                if item.get("status") == normalized_status
            ]

        incidents.sort(
            key=lambda item: str(item.get("last_seen_at") or ""),
            reverse=True,
        )

        return incidents[:normalized_limit]

    def list_snapshots(
        self,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 5000))

        snapshots = [
            deepcopy(item)
            for item in self.load().get("snapshots", [])
            if isinstance(item, Mapping)
        ]

        snapshots.sort(
            key=lambda item: str(item.get("captured_at") or ""),
            reverse=True,
        )

        return snapshots[:normalized_limit]

    def summary(self) -> dict[str, Any]:
        state = self.load()

        incidents = [
            item
            for item in state.get("incidents", [])
            if isinstance(item, Mapping)
        ]

        active = [
            item
            for item in incidents
            if item.get("status") == "ACTIVE"
        ]

        resolved = [
            item
            for item in incidents
            if item.get("status") == "RESOLVED"
        ]

        severity_counts = {
            severity: sum(
                1
                for item in active
                if item.get("severity") == severity
            )
            for severity in self.VALID_SEVERITIES
        }

        acknowledged_active = sum(
            1
            for item in active
            if item.get("acknowledged_at")
        )

        return {
            "status": "ok",
            "updated_at": state.get("updated_at"),
            "total_incidents": len(incidents),
            "active_incidents": len(active),
            "resolved_incidents": len(resolved),
            "active_critical": severity_counts["critical"],
            "active_warning": severity_counts["warning"],
            "active_info": severity_counts["info"],
            "acknowledged_active": acknowledged_active,
            "unacknowledged_active": len(active) - acknowledged_active,
            "total_snapshots": len(state.get("snapshots", [])),
            "journal_path": str(self.path),
            **self._safe_flags(),
        }
