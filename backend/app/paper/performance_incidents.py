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


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _iso_now() -> str:
    return _utc_now().isoformat()


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _safe_snapshot(
    snapshot: Mapping[str, Any],
) -> None:
    if snapshot.get("execution_authorized") is not False:
        raise ValueError(
            "Snapshot sem bloqueio explícito de execução."
        )

    if snapshot.get("live_execution") is not False:
        raise ValueError(
            "Snapshot com execução live não bloqueada."
        )

    if snapshot.get("read_only") is not True:
        raise ValueError(
            "Snapshot não está marcado como somente leitura."
        )


class PaperIncidentJournal:
    """Histórico persistente de alertas do monitor Paper."""

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_snapshots: int = 500,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "PAPER_MONITOR_INCIDENTS_PATH",
                "paper_data/paper_monitor_incidents.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.max_snapshots = max(
            10,
            min(int(max_snapshots), 5000),
        )

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": None,
            "incidents": [],
            "snapshots": [],
            "execution_authorized": False,
            "live_execution": False,
        }

    def load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return self._empty_state()

        payload = json.loads(
            self.path.read_text(encoding="utf-8")
        )

        if not isinstance(payload, dict):
            raise ValueError(
                "Arquivo de incidentes inválido."
            )

        payload.setdefault("version", 1)
        payload.setdefault("updated_at", None)
        payload.setdefault("incidents", [])
        payload.setdefault("snapshots", [])
        payload["execution_authorized"] = False
        payload["live_execution"] = False

        if not isinstance(payload["incidents"], list):
            raise ValueError(
                "Lista de incidentes inválida."
            )

        if not isinstance(payload["snapshots"], list):
            raise ValueError(
                "Lista de snapshots inválida."
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

        payload = deepcopy(dict(state))
        payload["execution_authorized"] = False
        payload["live_execution"] = False

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
                os.fsync(file.fileno())

            temp_path.replace(self.path)

        finally:
            if temp_path.exists():
                temp_path.unlink(
                    missing_ok=True
                )

    @staticmethod
    def _incident_id(
        alert: Mapping[str, Any],
    ) -> str:
        source = "|".join(
            (
                str(alert.get("code") or ""),
                str(alert.get("severity") or ""),
                str(alert.get("title") or ""),
            )
        )

        return hashlib.sha256(
            source.encode("utf-8")
        ).hexdigest()[:20]

    @staticmethod
    def _summary_from_state(
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
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

        return {
            "status": "ok",
            "journal_path": None,
            "updated_at": state.get("updated_at"),
            "total_incidents": len(incidents),
            "active_incidents": len(active),
            "resolved_incidents": len(resolved),
            "acknowledged_incidents": sum(
                1
                for item in incidents
                if item.get("acknowledged_at")
            ),
            "active_critical": sum(
                1
                for item in active
                if item.get("severity") == "critical"
            ),
            "active_warning": sum(
                1
                for item in active
                if item.get("severity") == "warning"
            ),
            "active_info": sum(
                1
                for item in active
                if item.get("severity") == "info"
            ),
            "snapshots": len(
                state.get("snapshots", [])
            ),
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        }

    def summary(self) -> dict[str, Any]:
        result = self._summary_from_state(
            self.load()
        )
        result["journal_path"] = str(
            self.path
        )
        return result

    def list_incidents(
        self,
        *,
        status: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 1000),
        )

        normalized_status = (
            status.strip().upper()
            if status
            else None
        )

        if normalized_status not in {
            None,
            "ACTIVE",
            "RESOLVED",
        }:
            raise ValueError(
                "Status deve ser ACTIVE ou RESOLVED."
            )

        incidents = [
            deepcopy(item)
            for item in self.load().get(
                "incidents",
                [],
            )
            if isinstance(item, Mapping)
        ]

        if normalized_status:
            incidents = [
                item
                for item in incidents
                if item.get("status")
                == normalized_status
            ]

        incidents.sort(
            key=lambda item: str(
                item.get("last_seen_at") or ""
            ),
            reverse=True,
        )

        return incidents[:normalized_limit]

    def capture(
        self,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        _safe_snapshot(snapshot)

        alerts = snapshot.get("alerts") or []

        if not isinstance(alerts, list):
            raise ValueError(
                "Lista de alertas inválida."
            )

        state = self.load()
        now = _iso_now()

        incidents = [
            dict(item)
            for item in state.get("incidents", [])
            if isinstance(item, Mapping)
        ]

        by_id = {
            str(item.get("id")): item
            for item in incidents
            if item.get("id")
        }

        observed_ids: set[str] = set()
        created: list[str] = []
        reactivated: list[str] = []
        resolved: list[str] = []

        for alert in alerts:
            if not isinstance(alert, Mapping):
                continue

            incident_id = self._incident_id(alert)
            observed_ids.add(incident_id)

            existing = by_id.get(incident_id)

            if existing is None:
                existing = {
                    "id": incident_id,
                    "code": alert.get("code"),
                    "severity": alert.get("severity"),
                    "title": alert.get("title"),
                    "message": alert.get("message"),
                    "current_value": alert.get(
                        "current_value"
                    ),
                    "threshold": alert.get("threshold"),
                    "status": "ACTIVE",
                    "first_seen_at": now,
                    "last_seen_at": now,
                    "resolved_at": None,
                    "acknowledged_at": None,
                    "occurrences": 1,
                }

                incidents.append(existing)
                by_id[incident_id] = existing
                created.append(incident_id)
                continue

            if existing.get("status") == "RESOLVED":
                existing["status"] = "ACTIVE"
                existing["resolved_at"] = None
                reactivated.append(incident_id)

            existing["severity"] = alert.get(
                "severity"
            )
            existing["title"] = alert.get("title")
            existing["message"] = alert.get(
                "message"
            )
            existing["current_value"] = alert.get(
                "current_value"
            )
            existing["threshold"] = alert.get(
                "threshold"
            )
            existing["last_seen_at"] = now
            existing["occurrences"] = (
                _integer(
                    existing.get("occurrences"),
                    0,
                )
                + 1
            )

        for incident in incidents:
            incident_id = str(
                incident.get("id") or ""
            )

            if (
                incident.get("status") == "ACTIVE"
                and incident_id not in observed_ids
            ):
                incident["status"] = "RESOLVED"
                incident["resolved_at"] = now
                resolved.append(incident_id)

        snapshot_entry = {
            "captured_at": now,
            "monitor_status": snapshot.get("status"),
            "monitor_score": snapshot.get("score"),
            "alert_count": len(alerts),
            "active_incident_ids": sorted(
                observed_ids
            ),
            "execution_authorized": False,
            "live_execution": False,
        }

        snapshots = [
            item
            for item in state.get("snapshots", [])
            if isinstance(item, Mapping)
        ]

        snapshots.append(snapshot_entry)
        snapshots = snapshots[
            -self.max_snapshots:
        ]

        state.update(
            {
                "updated_at": now,
                "incidents": incidents,
                "snapshots": snapshots,
                "execution_authorized": False,
                "live_execution": False,
            }
        )

        self._save(state)

        summary = self._summary_from_state(
            state
        )
        summary["journal_path"] = str(
            self.path
        )

        return {
            "status": "captured",
            "captured_at": now,
            "created": created,
            "reactivated": reactivated,
            "resolved": resolved,
            "summary": summary,
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        }

    def acknowledge(
        self,
        incident_id: str,
    ) -> dict[str, Any]:
        state = self.load()
        now = _iso_now()

        target = None

        for incident in state.get(
            "incidents",
            [],
        ):
            if (
                isinstance(incident, dict)
                and incident.get("id")
                == incident_id
            ):
                target = incident
                break

        if target is None:
            raise KeyError(incident_id)

        target["acknowledged_at"] = now
        state["updated_at"] = now
        self._save(state)

        return {
            "status": "acknowledged",
            "incident": deepcopy(target),
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        }

    def snapshots(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 1000),
        )

        values = [
            deepcopy(item)
            for item in self.load().get(
                "snapshots",
                [],
            )
            if isinstance(item, Mapping)
        ]

        return values[
            -normalized_limit:
        ]
