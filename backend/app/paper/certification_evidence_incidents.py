from __future__ import annotations

import hashlib
import json
import os
import tempfile
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[2]


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


class PaperCertificationEvidenceIncidentJournal:
    """Journal persistente dos alertas do monitor de evidências."""

    VALID_STATUSES = {
        "ACTIVE",
        "RESOLVED",
    }

    VALID_SEVERITIES = {
        "critical",
        "warning",
        "info",
    }

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_snapshots: int = 1000,
        max_incidents: int = 5000,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "PAPER_EVIDENCE_INCIDENTS_PATH",
                "paper_data/"
                "paper_certification_evidence_incidents.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = (
                BACKEND_ROOT / candidate
            )

        self.path = candidate.resolve()
        self.max_snapshots = max(
            10,
            min(
                int(max_snapshots),
                10000,
            ),
        )
        self.max_incidents = max(
            10,
            min(
                int(max_incidents),
                50000,
            ),
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
    def _empty_state(
        cls,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": None,
            "incidents": [],
            "snapshots": [],
            **cls._safe_flags(),
        }

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty_state()

        payload = json.loads(
            self.path.read_text(
                encoding="utf-8"
            )
        )

        if not isinstance(payload, dict):
            raise ValueError(
                "Arquivo de incidentes inválido."
            )

        payload.setdefault("version", 1)
        payload.setdefault("updated_at", None)
        payload.setdefault("incidents", [])
        payload.setdefault("snapshots", [])

        if not isinstance(
            payload["incidents"],
            list,
        ):
            raise ValueError(
                "Lista de incidentes inválida."
            )

        if not isinstance(
            payload["snapshots"],
            list,
        ):
            raise ValueError(
                "Lista de snapshots inválida."
            )

        payload.update(
            self._safe_flags()
        )

        return payload

    def _save(
        self,
        state: Mapping[str, Any],
    ) -> None:
        self.path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        payload = deepcopy(
            dict(state)
        )
        payload.update(
            self._safe_flags()
        )

        handle, temp_name = tempfile.mkstemp(
            prefix=f"{self.path.stem}_",
            suffix=".tmp",
            dir=str(self.path.parent),
        )

        temp_path = Path(temp_name)

        try:
            with os.fdopen(
                handle,
                "w",
                encoding="utf-8",
            ) as file:
                json.dump(
                    payload,
                    file,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                file.flush()
                os.fsync(
                    file.fileno()
                )

            temp_path.replace(
                self.path
            )

        finally:
            temp_path.unlink(
                missing_ok=True
            )

    @staticmethod
    def _validate_snapshot(
        snapshot: Mapping[str, Any],
    ) -> None:
        required_false = (
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if snapshot.get(
                field
            ) is not False:
                raise ValueError(
                    f"{field} não está "
                    "explicitamente bloqueado."
                )

        if snapshot.get(
            "read_only"
        ) is not True:
            raise ValueError(
                "Snapshot não está marcado "
                "como somente leitura."
            )

        alerts = snapshot.get(
            "alerts"
        )

        if not isinstance(
            alerts,
            list,
        ):
            raise ValueError(
                "Lista de alertas inválida."
            )

    @classmethod
    def _incident_id(
        cls,
        alert: Mapping[str, Any],
    ) -> str:
        raw = "|".join(
            (
                str(
                    alert.get("code")
                    or "UNKNOWN"
                ),
                str(
                    alert.get("severity")
                    or "unknown"
                ),
                str(
                    alert.get("title")
                    or ""
                ),
            )
        )

        digest = hashlib.sha256(
            raw.encode("utf-8")
        ).hexdigest()

        return (
            "evidence-incident-"
            + digest[:24]
        )

    @classmethod
    def _normalize_alert(
        cls,
        alert: Mapping[str, Any],
    ) -> dict[str, Any]:
        code = str(
            alert.get("code")
            or ""
        ).strip()

        severity = str(
            alert.get("severity")
            or ""
        ).strip().lower()

        title = str(
            alert.get("title")
            or ""
        ).strip()

        if not code:
            raise ValueError(
                "Alerta sem código."
            )

        if severity not in (
            cls.VALID_SEVERITIES
        ):
            raise ValueError(
                "Severidade de alerta inválida."
            )

        if not title:
            raise ValueError(
                "Alerta sem título."
            )

        return {
            "code": code,
            "severity": severity,
            "title": title,
            "message": str(
                alert.get("message")
                or ""
            ),
            "current_value": deepcopy(
                alert.get(
                    "current_value"
                )
            ),
            "threshold": deepcopy(
                alert.get("threshold")
            ),
        }

    @classmethod
    def _new_incident(
        cls,
        alert: Mapping[str, Any],
        *,
        now: str,
    ) -> dict[str, Any]:
        normalized = (
            cls._normalize_alert(
                alert
            )
        )

        return {
            "id": cls._incident_id(
                normalized
            ),
            "status": "ACTIVE",
            **normalized,
            "first_seen_at": now,
            "last_seen_at": now,
            "resolved_at": None,
            "reactivated_at": None,
            "occurrences": 1,
            "reactivations": 0,
            "acknowledged": False,
            "acknowledged_at": None,
            "acknowledged_by": None,
            "acknowledgement_note": None,
            **cls._safe_flags(),
        }

    @classmethod
    def _compact_snapshot(
        cls,
        snapshot: Mapping[str, Any],
        *,
        captured_at: str,
    ) -> dict[str, Any]:
        diagnostics = (
            snapshot.get("diagnostics")
            or {}
        )

        counts = (
            snapshot.get("alert_counts")
            or {}
        )

        return {
            "captured_at": captured_at,
            "monitor_generated_at": (
                snapshot.get(
                    "generated_at"
                )
            ),
            "status": snapshot.get(
                "status"
            ),
            "score": snapshot.get(
                "score"
            ),
            "critical_alerts": _integer(
                counts.get("critical")
            ),
            "warning_alerts": _integer(
                counts.get("warning")
            ),
            "info_alerts": _integer(
                counts.get("info")
            ),
            "total_entries": _integer(
                diagnostics.get(
                    "total_entries"
                )
            ),
            "chain_status": diagnostics.get(
                "chain_status"
            ),
            "chain_valid": diagnostics.get(
                "chain_valid"
            ),
            "latest_status": diagnostics.get(
                "latest_status"
            ),
            **cls._safe_flags(),
        }

    @classmethod
    def _summary_from_state(
        cls,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        incidents = [
            item
            for item in state.get(
                "incidents",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        snapshots = [
            item
            for item in state.get(
                "snapshots",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        active = [
            item
            for item in incidents
            if item.get("status")
            == "ACTIVE"
        ]

        resolved = [
            item
            for item in incidents
            if item.get("status")
            == "RESOLVED"
        ]

        return {
            "status": "ok",
            "updated_at": state.get(
                "updated_at"
            ),
            "total_incidents": len(
                incidents
            ),
            "active_incidents": len(
                active
            ),
            "resolved_incidents": len(
                resolved
            ),
            "active_critical": sum(
                1
                for item in active
                if item.get("severity")
                == "critical"
            ),
            "active_warning": sum(
                1
                for item in active
                if item.get("severity")
                == "warning"
            ),
            "active_info": sum(
                1
                for item in active
                if item.get("severity")
                == "info"
            ),
            "acknowledged_incidents": sum(
                1
                for item in incidents
                if item.get(
                    "acknowledged"
                )
                is True
            ),
            "snapshots": len(
                snapshots
            ),
            **cls._safe_flags(),
        }

    def summary(
        self,
    ) -> dict[str, Any]:
        state = self.load()
        result = self._summary_from_state(
            state
        )
        result["journal_path"] = str(
            self.path
        )

        return result

    def capture(
        self,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_snapshot(
            snapshot
        )

        state = self.load()
        now = _utc_now()

        incidents = [
            dict(item)
            for item in state.get(
                "incidents",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        snapshots = [
            dict(item)
            for item in state.get(
                "snapshots",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        by_id = {
            str(item.get("id")): item
            for item in incidents
            if item.get("id")
        }

        current_ids: set[str] = set()
        created: list[str] = []
        updated: list[str] = []
        reactivated: list[str] = []
        resolved: list[str] = []

        for raw_alert in (
            snapshot.get("alerts")
            or []
        ):
            if not isinstance(
                raw_alert,
                Mapping,
            ):
                raise ValueError(
                    "Alerta inválido."
                )

            normalized = (
                self._normalize_alert(
                    raw_alert
                )
            )

            incident_id = (
                self._incident_id(
                    normalized
                )
            )

            current_ids.add(
                incident_id
            )

            incident = by_id.get(
                incident_id
            )

            if incident is None:
                incident = (
                    self._new_incident(
                        normalized,
                        now=now,
                    )
                )
                incidents.append(
                    incident
                )
                by_id[
                    incident_id
                ] = incident
                created.append(
                    incident_id
                )
                continue

            was_resolved = (
                incident.get("status")
                == "RESOLVED"
            )

            incident.update(
                {
                    **normalized,
                    "status": "ACTIVE",
                    "last_seen_at": now,
                    "resolved_at": None,
                    "occurrences": (
                        _integer(
                            incident.get(
                                "occurrences"
                            ),
                            0,
                        )
                        + 1
                    ),
                    **self._safe_flags(),
                }
            )

            if was_resolved:
                incident[
                    "reactivated_at"
                ] = now
                incident[
                    "reactivations"
                ] = (
                    _integer(
                        incident.get(
                            "reactivations"
                        ),
                        0,
                    )
                    + 1
                )
                reactivated.append(
                    incident_id
                )
            else:
                updated.append(
                    incident_id
                )

        for incident in incidents:
            incident_id = str(
                incident.get("id")
                or ""
            )

            if (
                incident.get("status")
                == "ACTIVE"
                and incident_id
                not in current_ids
            ):
                incident[
                    "status"
                ] = "RESOLVED"
                incident[
                    "resolved_at"
                ] = now
                incident.update(
                    self._safe_flags()
                )
                resolved.append(
                    incident_id
                )

        snapshots.append(
            self._compact_snapshot(
                snapshot,
                captured_at=now,
            )
        )

        incidents = incidents[
            -self.max_incidents:
        ]

        snapshots = snapshots[
            -self.max_snapshots:
        ]

        state.update(
            {
                "updated_at": now,
                "incidents": incidents,
                "snapshots": snapshots,
                **self._safe_flags(),
            }
        )

        self._save(state)

        return {
            "status": "captured",
            "created": created,
            "updated": updated,
            "reactivated": reactivated,
            "resolved": resolved,
            "summary": (
                self._summary_from_state(
                    state
                )
            ),
            **self._safe_flags(),
        }

    def list_incidents(
        self,
        *,
        status: str | None = None,
        severity: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(
                int(limit),
                5000,
            ),
        )

        normalized_status = (
            str(status)
            .strip()
            .upper()
            if status
            else None
        )

        normalized_severity = (
            str(severity)
            .strip()
            .lower()
            if severity
            else None
        )

        if (
            normalized_status
            is not None
            and normalized_status
            not in self.VALID_STATUSES
        ):
            raise ValueError(
                "Status de incidente inválido."
            )

        if (
            normalized_severity
            is not None
            and normalized_severity
            not in self.VALID_SEVERITIES
        ):
            raise ValueError(
                "Severidade inválida."
            )

        incidents = [
            deepcopy(item)
            for item in self.load().get(
                "incidents",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        if normalized_status:
            incidents = [
                item
                for item in incidents
                if item.get("status")
                == normalized_status
            ]

        if normalized_severity:
            incidents = [
                item
                for item in incidents
                if item.get("severity")
                == normalized_severity
            ]

        incidents.sort(
            key=lambda item: str(
                item.get(
                    "last_seen_at"
                )
                or item.get(
                    "resolved_at"
                )
                or ""
            ),
            reverse=True,
        )

        return incidents[
            :normalized_limit
        ]

    def get_incident(
        self,
        incident_id: str,
    ) -> dict[str, Any] | None:
        for incident in (
            self.list_incidents(
                limit=5000
            )
        ):
            if incident.get(
                "id"
            ) == incident_id:
                return incident

        return None

    def list_snapshots(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(
                int(limit),
                5000,
            ),
        )

        snapshots = [
            deepcopy(item)
            for item in self.load().get(
                "snapshots",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        snapshots.sort(
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
            reverse=True,
        )

        return snapshots[
            :normalized_limit
        ]

    def acknowledge(
        self,
        incident_id: str,
        *,
        acknowledged_by: str = "operator",
        note: str | None = None,
    ) -> dict[str, Any]:
        state = self.load()
        now = _utc_now()

        found = None

        for incident in state.get(
            "incidents",
            [],
        ):
            if (
                isinstance(
                    incident,
                    dict,
                )
                and incident.get("id")
                == incident_id
            ):
                found = incident
                break

        if found is None:
            raise KeyError(
                incident_id
            )

        found.update(
            {
                "acknowledged": True,
                "acknowledged_at": now,
                "acknowledged_by": (
                    str(
                        acknowledged_by
                        or "operator"
                    )[:120]
                ),
                "acknowledgement_note": (
                    str(note)[:1000]
                    if note
                    else None
                ),
                **self._safe_flags(),
            }
        )

        state["updated_at"] = now
        state.update(
            self._safe_flags()
        )

        self._save(state)

        return {
            "status": "acknowledged",
            "incident": deepcopy(
                found
            ),
            **self._safe_flags(),
        }
