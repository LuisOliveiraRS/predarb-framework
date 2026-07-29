from __future__ import annotations

import hashlib
import json
import os
import tempfile
import threading
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[2]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _canonical_json(payload: Mapping[str, Any]) -> str:
    return json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )


def _sha256(payload: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        _canonical_json(payload).encode("utf-8")
    ).hexdigest()


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


class FinalPaperValidationEvidence:
    """Arquivo probatório encadeado da validação final Paper."""

    VALID_STATUSES = {
        "PAPER_VALIDATED",
        "PAPER_PENDING",
        "PAPER_BLOCKED",
        "INSUFFICIENT_DATA",
    }

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
                "PAPER_FINAL_VALIDATION_EVIDENCE_PATH",
                "paper_data/final_paper_validation_evidence.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.max_entries = max(1, min(int(max_entries), 50000))
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
            "chain_head": None,
            "entries": [],
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
                raise ValueError(
                    f"{name}: {field} não está explicitamente bloqueado."
                )

        if payload.get("read_only") is not True:
            raise ValueError(
                f"{name}: payload não está marcado como somente leitura."
            )

    @classmethod
    def _validate_report(
        cls,
        report: Mapping[str, Any],
    ) -> None:
        status = str(report.get("status") or "").upper()

        if status not in cls.VALID_STATUSES:
            raise ValueError("Status da validação final inválido.")

        if report.get("scope") != "PAPER_VALIDATION_ONLY":
            raise ValueError(
                "O relatório deve ter escopo PAPER_VALIDATION_ONLY."
            )

        cls._validate_safety("final_validation_report", report)

        if not isinstance(report.get("checks"), list):
            raise ValueError("Lista de checks da validação final inválida.")

        if not isinstance(report.get("failures"), list):
            raise ValueError("Lista de falhas da validação final inválida.")

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return self._empty_state()

            payload = json.loads(
                self.path.read_text(encoding="utf-8")
            )

            if not isinstance(payload, dict):
                raise ValueError(
                    "Arquivo de evidências da validação final inválido."
                )

            payload.setdefault("version", 1)
            payload.setdefault("created_at", None)
            payload.setdefault("updated_at", None)
            payload.setdefault("chain_head", None)
            payload.setdefault("entries", [])

            if not isinstance(payload["entries"], list):
                raise ValueError(
                    "Lista de evidências da validação final inválida."
                )

            self._validate_safety("evidence_state", payload)
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
                )
                file.flush()
                os.fsync(file.fileno())

            temp_path.replace(self.path)

        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _compact_payload(
        cls,
        report: Mapping[str, Any],
        *,
        evidence_id: str,
        captured_at: str,
        previous_hash: str | None,
    ) -> dict[str, Any]:
        summary = report.get("summary") or {}
        thresholds = report.get("thresholds") or {}

        failures = [
            item
            for item in (report.get("failures") or [])
            if isinstance(item, Mapping)
        ]

        return {
            "id": evidence_id,
            "captured_at": captured_at,
            "previous_hash": previous_hash,
            "report_generated_at": report.get("generated_at"),
            "status": str(report.get("status")).upper(),
            "validated": report.get("validated") is True,
            "scope": "PAPER_VALIDATION_ONLY",
            "validation_score": round(
                _number(report.get("validation_score")),
                8,
            ),
            "summary": {
                "total_checks": _integer(summary.get("total_checks")),
                "passed_checks": _integer(summary.get("passed_checks")),
                "failed_checks": _integer(summary.get("failed_checks")),
                "failed_data_checks": _integer(
                    summary.get("failed_data_checks")
                ),
                "failed_validation_checks": _integer(
                    summary.get("failed_validation_checks")
                ),
                "assurance_status": summary.get("assurance_status"),
                "assurance_score": _number(
                    summary.get("assurance_score")
                ),
                "gate_status": summary.get("gate_status"),
                "gate_score": _number(summary.get("gate_score")),
                "gate_history_entries": _integer(
                    summary.get("gate_history_entries")
                ),
                "gate_history_latest_status": summary.get(
                    "gate_history_latest_status"
                ),
                "qualified_streak": _integer(
                    summary.get("qualified_streak")
                ),
                "total_runtime_failures": _integer(
                    summary.get("total_runtime_failures")
                ),
            },
            "thresholds": deepcopy(dict(thresholds)),
            "failure_codes": [
                str(item.get("code") or "UNKNOWN")
                for item in failures
            ],
            **cls._safe_flags(),
        }

    @classmethod
    def _hashable_entry(
        cls,
        entry: Mapping[str, Any],
    ) -> dict[str, Any]:
        return {
            key: deepcopy(value)
            for key, value in entry.items()
            if key != "entry_hash"
        }

    @classmethod
    def _validate_entry_shape(
        cls,
        entry: Mapping[str, Any],
    ) -> None:
        if str(entry.get("status") or "").upper() not in cls.VALID_STATUSES:
            raise ValueError("Status de evidência inválido.")

        if entry.get("scope") != "PAPER_VALIDATION_ONLY":
            raise ValueError("Escopo de evidência inválido.")

        if not isinstance(entry.get("entry_hash"), str):
            raise ValueError("Hash da evidência ausente.")

        cls._validate_safety("evidence_entry", entry)

    def verify(self) -> dict[str, Any]:
        try:
            state = self.load()
            entries = state.get("entries") or []

            if not entries:
                return {
                    "integrity_status": "EMPTY",
                    "valid": True,
                    "entry_count": 0,
                    "chain_head": None,
                    "broken_index": None,
                    "reason": None,
                    **self._safe_flags(),
                }

            previous_hash = None

            for index, raw_entry in enumerate(entries):
                if not isinstance(raw_entry, Mapping):
                    raise ValueError(
                        f"Entrada {index} não é um objeto."
                    )

                entry = dict(raw_entry)
                self._validate_entry_shape(entry)

                if entry.get("previous_hash") != previous_hash:
                    return {
                        "integrity_status": "BROKEN",
                        "valid": False,
                        "entry_count": len(entries),
                        "chain_head": state.get("chain_head"),
                        "broken_index": index,
                        "reason": "previous_hash divergente",
                        **self._safe_flags(),
                    }

                calculated = _sha256(
                    self._hashable_entry(entry)
                )

                if entry.get("entry_hash") != calculated:
                    return {
                        "integrity_status": "BROKEN",
                        "valid": False,
                        "entry_count": len(entries),
                        "chain_head": state.get("chain_head"),
                        "broken_index": index,
                        "reason": "entry_hash divergente",
                        **self._safe_flags(),
                    }

                previous_hash = calculated

            if state.get("chain_head") != previous_hash:
                return {
                    "integrity_status": "BROKEN",
                    "valid": False,
                    "entry_count": len(entries),
                    "chain_head": state.get("chain_head"),
                    "broken_index": len(entries) - 1,
                    "reason": "chain_head divergente",
                    **self._safe_flags(),
                }

            return {
                "integrity_status": "VALID",
                "valid": True,
                "entry_count": len(entries),
                "chain_head": previous_hash,
                "broken_index": None,
                "reason": None,
                **self._safe_flags(),
            }

        except Exception as exc:
            return {
                "integrity_status": "BROKEN",
                "valid": False,
                "entry_count": 0,
                "chain_head": None,
                "broken_index": None,
                "reason": str(exc),
                **self._safe_flags(),
            }

    def capture(
        self,
        report: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_report(report)

        with self._lock:
            state = self.load()
            integrity = self.verify()

            if integrity["integrity_status"] == "BROKEN":
                raise RuntimeError(
                    "O arquivo de evidências está corrompido. "
                    "Nova captura foi bloqueada."
                )

            entries = [
                dict(item)
                for item in state.get("entries", [])
                if isinstance(item, Mapping)
            ]

            if len(entries) >= self.max_entries:
                raise RuntimeError(
                    "O limite do arquivo de evidências foi atingido. "
                    "A cadeia não será truncada automaticamente."
                )

            captured_at = _utc_now()
            evidence_id = uuid.uuid4().hex
            previous_hash = state.get("chain_head")

            entry = self._compact_payload(
                report,
                evidence_id=evidence_id,
                captured_at=captured_at,
                previous_hash=previous_hash,
            )

            entry["entry_hash"] = _sha256(
                self._hashable_entry(entry)
            )

            entries.append(entry)

            state.update(
                {
                    "created_at": state.get("created_at") or captured_at,
                    "updated_at": captured_at,
                    "chain_head": entry["entry_hash"],
                    "entries": entries,
                    **self._safe_flags(),
                }
            )

            self._save(state)

            return {
                "status": "captured",
                "evidence": deepcopy(entry),
                "summary": self.summary(),
                "integrity": self.verify(),
                **self._safe_flags(),
            }

    def list_entries(
        self,
        *,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(1, min(int(limit), 5000))

        entries = [
            deepcopy(item)
            for item in self.load().get("entries", [])
            if isinstance(item, Mapping)
        ]

        entries.sort(
            key=lambda item: str(item.get("captured_at") or ""),
            reverse=True,
        )

        return entries[:normalized_limit]

    def latest(self) -> dict[str, Any] | None:
        entries = self.list_entries(limit=1)
        return entries[0] if entries else None

    def summary(self) -> dict[str, Any]:
        state = self.load()
        entries = [
            item
            for item in state.get("entries", [])
            if isinstance(item, Mapping)
        ]

        counts = {
            status: sum(
                1
                for item in entries
                if item.get("status") == status
            )
            for status in self.VALID_STATUSES
        }

        latest = (
            max(
                entries,
                key=lambda item: str(item.get("captured_at") or ""),
            )
            if entries
            else None
        )

        integrity = self.verify()

        return {
            "status": "ok",
            "total_entries": len(entries),
            "status_counts": counts,
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
            "latest_status": latest.get("status") if latest else None,
            "latest_score": (
                _number(latest.get("validation_score"))
                if latest
                else None
            ),
            "chain_head": state.get("chain_head"),
            "integrity_status": integrity["integrity_status"],
            "integrity_valid": integrity["valid"],
            "evidence_path": str(self.path),
            **self._safe_flags(),
        }
