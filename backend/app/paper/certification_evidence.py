from __future__ import annotations

import hashlib
import json
import os
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[2]


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


def _canonical_json(
    payload: Mapping[str, Any],
) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


class PaperCertificationEvidence:
    """Arquivo encadeado de evidências da certificação Paper."""

    VALID_STATUSES = {
        "CERTIFIED",
        "PENDING",
        "BLOCKED",
        "NO_DATA",
    }

    GENESIS_HASH = "0" * 64

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_entries: int = 5000,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "PAPER_CERTIFICATION_EVIDENCE_PATH",
                "paper_data/paper_certification_evidence.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.max_entries = max(
            10,
            min(int(max_entries), 50000),
        )

    @classmethod
    def _empty_state(
        cls,
    ) -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": None,
            "entries": [],
            "chain_head": cls.GENESIS_HASH,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "live_authorization": False,
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
                "Arquivo de evidências inválido."
            )

        payload.setdefault("version", 1)
        payload.setdefault("updated_at", None)
        payload.setdefault("entries", [])
        payload.setdefault(
            "chain_head",
            self.GENESIS_HASH,
        )

        if not isinstance(
            payload["entries"],
            list,
        ):
            raise ValueError(
                "Lista de evidências inválida."
            )

        payload["execution_authorized"] = False
        payload["live_execution"] = False
        payload["financial_execution"] = False
        payload["live_authorization"] = False

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
        payload["financial_execution"] = False
        payload["live_authorization"] = False

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
            temp_path.unlink(
                missing_ok=True
            )

    @classmethod
    def _validate_report(
        cls,
        report: Mapping[str, Any],
    ) -> None:
        status = str(
            report.get("status") or ""
        ).upper()

        if status not in cls.VALID_STATUSES:
            raise ValueError(
                "Status de certificação inválido."
            )

        if report.get("scope") != "PAPER_ONLY":
            raise ValueError(
                "A certificação deve ter escopo PAPER_ONLY."
            )

        required_false = (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if report.get(field) is not False:
                raise ValueError(
                    f"{field} não está explicitamente bloqueado."
                )

        if report.get("read_only") is not True:
            raise ValueError(
                "Relatório não está marcado como somente leitura."
            )

    @staticmethod
    def _evidence_payload(
        report: Mapping[str, Any],
        *,
        evidence_id: str,
        captured_at: str,
        previous_hash: str,
    ) -> dict[str, Any]:
        summary = report.get("summary") or {}

        return {
            "id": evidence_id,
            "captured_at": captured_at,
            "report_generated_at": report.get(
                "generated_at"
            ),
            "status": str(
                report.get("status")
            ).upper(),
            "certified": bool(
                report.get("certified")
            ),
            "scope": "PAPER_ONLY",
            "certification_score": _number(
                report.get(
                    "certification_score"
                )
            ),
            "thresholds": deepcopy(
                report.get("thresholds") or {}
            ),
            "summary": {
                "total_checks": _integer(
                    summary.get("total_checks")
                ),
                "passed_checks": _integer(
                    summary.get("passed_checks")
                ),
                "pending_checks": _integer(
                    summary.get("pending_checks")
                ),
                "blockers": _integer(
                    summary.get("blockers")
                ),
                "total_history_entries": _integer(
                    summary.get(
                        "total_history_entries"
                    )
                ),
                "latest_status": summary.get(
                    "latest_status"
                ),
                "latest_score": _number(
                    summary.get("latest_score")
                ),
                "recent_average_score": _number(
                    summary.get(
                        "recent_average_score"
                    )
                ),
                "consecutive_ready": _integer(
                    summary.get(
                        "consecutive_ready"
                    )
                ),
                "recent_not_ready": _integer(
                    summary.get(
                        "recent_not_ready"
                    )
                ),
            },
            "blocker_codes": [
                str(item.get("code"))
                for item in (
                    report.get("blockers")
                    or []
                )
                if isinstance(item, Mapping)
                and item.get("code")
            ],
            "pending_codes": [
                str(item.get("code"))
                for item in (
                    report.get("pending")
                    or []
                )
                if isinstance(item, Mapping)
                and item.get("code")
            ],
            "previous_hash": previous_hash,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    @staticmethod
    def _calculate_hash(
        payload: Mapping[str, Any],
    ) -> str:
        data = {
            key: value
            for key, value in payload.items()
            if key != "evidence_hash"
        }

        return hashlib.sha256(
            _canonical_json(data).encode(
                "utf-8"
            )
        ).hexdigest()

    def capture(
        self,
        report: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_report(report)

        state = self.load()
        entries = [
            dict(item)
            for item in state.get(
                "entries",
                [],
            )
            if isinstance(item, Mapping)
        ]

        previous_hash = (
            str(entries[-1].get("evidence_hash"))
            if entries
            else self.GENESIS_HASH
        )

        evidence = self._evidence_payload(
            report,
            evidence_id=uuid.uuid4().hex,
            captured_at=_utc_now(),
            previous_hash=previous_hash,
        )

        evidence["evidence_hash"] = (
            self._calculate_hash(evidence)
        )

        entries.append(evidence)
        entries = entries[
            -self.max_entries:
        ]

        state.update(
            {
                "updated_at": _utc_now(),
                "entries": entries,
                "chain_head": evidence[
                    "evidence_hash"
                ],
                "execution_authorized": False,
                "live_execution": False,
                "financial_execution": False,
                "live_authorization": False,
            }
        )

        self._save(state)

        return {
            "status": "captured",
            "evidence": deepcopy(evidence),
            "verification": self.verify_state(
                state
            ),
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    def list_entries(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 5000),
        )

        entries = [
            deepcopy(item)
            for item in self.load().get(
                "entries",
                [],
            )
            if isinstance(item, Mapping)
        ]

        entries.sort(
            key=lambda item: str(
                item.get("captured_at")
                or ""
            ),
            reverse=True,
        )

        return entries[:normalized_limit]

    def latest(
        self,
    ) -> dict[str, Any] | None:
        entries = self.list_entries(
            limit=1
        )

        return entries[0] if entries else None

    @classmethod
    def verify_state(
        cls,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        entries = [
            item
            for item in state.get(
                "entries",
                [],
            )
            if isinstance(item, Mapping)
        ]

        expected_previous = cls.GENESIS_HASH
        broken_index = None
        broken_reason = None

        for index, entry in enumerate(entries):
            actual_previous = str(
                entry.get("previous_hash")
                or ""
            )

            if actual_previous != expected_previous:
                broken_index = index
                broken_reason = (
                    "previous_hash inválido"
                )
                break

            actual_hash = str(
                entry.get("evidence_hash")
                or ""
            )

            calculated_hash = (
                cls._calculate_hash(entry)
            )

            if actual_hash != calculated_hash:
                broken_index = index
                broken_reason = (
                    "evidence_hash inválido"
                )
                break

            expected_previous = actual_hash

        chain_head = str(
            state.get("chain_head")
            or cls.GENESIS_HASH
        )

        if (
            broken_index is None
            and chain_head != expected_previous
        ):
            broken_index = len(entries)
            broken_reason = (
                "chain_head inválido"
            )

        if not entries and broken_index is None:
            status = "EMPTY"

        elif broken_index is None:
            status = "VALID"

        else:
            status = "BROKEN"

        return {
            "status": status,
            "valid": status in {
                "VALID",
                "EMPTY",
            },
            "entries_checked": (
                len(entries)
                if broken_index is None
                else broken_index
            ),
            "total_entries": len(entries),
            "broken_index": broken_index,
            "broken_reason": broken_reason,
            "chain_head": chain_head,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    def verify(
        self,
    ) -> dict[str, Any]:
        return self.verify_state(
            self.load()
        )

    def summary(
        self,
    ) -> dict[str, Any]:
        state = self.load()

        entries = [
            item
            for item in state.get(
                "entries",
                [],
            )
            if isinstance(item, Mapping)
        ]

        certified = sum(
            1
            for item in entries
            if item.get("status")
            == "CERTIFIED"
        )

        pending = sum(
            1
            for item in entries
            if item.get("status")
            == "PENDING"
        )

        blocked = sum(
            1
            for item in entries
            if item.get("status")
            == "BLOCKED"
        )

        no_data = sum(
            1
            for item in entries
            if item.get("status")
            == "NO_DATA"
        )

        latest = (
            entries[-1]
            if entries
            else None
        )

        verification = self.verify_state(
            state
        )

        return {
            "status": "ok",
            "evidence_path": str(self.path),
            "updated_at": state.get(
                "updated_at"
            ),
            "total_entries": len(entries),
            "certified_entries": certified,
            "pending_entries": pending,
            "blocked_entries": blocked,
            "no_data_entries": no_data,
            "latest_status": (
                latest.get("status")
                if latest
                else None
            ),
            "latest_score": (
                _number(
                    latest.get(
                        "certification_score"
                    )
                )
                if latest
                else None
            ),
            "latest_hash": (
                latest.get("evidence_hash")
                if latest
                else None
            ),
            "chain_status": verification[
                "status"
            ],
            "chain_valid": verification[
                "valid"
            ],
            "chain_head": state.get(
                "chain_head"
            ),
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }
