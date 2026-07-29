from __future__ import annotations

import hashlib
import json
import os
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping
from uuid import uuid4


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class ShadowExecutionAuditRepository:
    """
    Repositorio append-only para auditoria de Shadow Execution.

    Este componente apenas registra eventos simulados.
    Ele nao importa exchanges, connectors, OMS ou executores live.
    """

    SCHEMA_VERSION = 1

    PROTECTED_FALSE_FLAGS = (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized",
    )

    SAFETY_FLAGS = {
        "market_data_only": True,
        "read_only_market_access": True,
        "shadow_execution": True,
        "simulation_only": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }

    def __init__(
        self,
        path: str | Path = (
            "paper_data/shadow_execution_audit.jsonl"
        ),
    ) -> None:
        self.path = Path(path)

        if self.path.suffix.lower() != ".jsonl":
            raise ValueError(
                "O arquivo de auditoria Shadow deve usar extensao .jsonl."
            )

        self._lock = RLock()
        self.last_appended_at: str | None = None
        self.last_verified_at: str | None = None

    @staticmethod
    def _canonical(payload: Mapping[str, Any]) -> str:
        return json.dumps(
            dict(payload),
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        )

    @classmethod
    def _calculate_hash(
        cls,
        record_without_hash: Mapping[str, Any],
    ) -> str:
        encoded = cls._canonical(
            record_without_hash
        ).encode("utf-8")

        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def _validate_payload_safety(
        cls,
        payload: Mapping[str, Any],
    ) -> None:
        for flag in cls.PROTECTED_FALSE_FLAGS:
            if (
                flag in payload
                and payload[flag] is not False
            ):
                raise ValueError(
                    f"A flag protegida {flag!r} deve permanecer False."
                )

    def exists(self) -> bool:
        return self.path.is_file()

    def _read_unlocked(self) -> list[dict[str, Any]]:
        if not self.exists():
            return []

        records: list[dict[str, Any]] = []

        with self.path.open(
            "r",
            encoding="utf-8",
        ) as handle:
            for line_number, raw_line in enumerate(
                handle,
                start=1,
            ):
                line = raw_line.strip()

                if not line:
                    continue

                try:
                    record = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(
                        "Linha JSONL invalida na auditoria Shadow: "
                        f"{line_number}."
                    ) from exc

                if not isinstance(record, Mapping):
                    raise ValueError(
                        "Registro Shadow invalido na linha "
                        f"{line_number}."
                    )

                records.append(dict(record))

        return records

    def append(
        self,
        payload: Mapping[str, Any],
        *,
        event_type: str = "SHADOW_EXECUTION",
    ) -> dict[str, Any]:
        if not isinstance(payload, Mapping):
            raise TypeError(
                "O payload Shadow deve ser um mapeamento."
            )

        resolved_payload = deepcopy(
            dict(payload)
        )

        self._validate_payload_safety(
            resolved_payload
        )

        resolved_event_type = str(
            event_type or "SHADOW_EXECUTION"
        ).strip().upper()

        if not resolved_event_type:
            raise ValueError(
                "event_type nao pode ser vazio."
            )

        with self._lock:
            current_records = self._read_unlocked()

            previous_hash = (
                current_records[-1].get("record_hash")
                if current_records
                else None
            )

            record: dict[str, Any] = {
                "schema_version": self.SCHEMA_VERSION,
                "sequence": len(current_records) + 1,
                "audit_id": str(uuid4()),
                "recorded_at": _utc_now(),
                "event_type": resolved_event_type,
                "previous_hash": previous_hash,
                "payload": resolved_payload,
                "safety": deepcopy(
                    self.SAFETY_FLAGS
                ),
            }

            record["record_hash"] = (
                self._calculate_hash(record)
            )

            encoded = json.dumps(
                record,
                ensure_ascii=False,
                sort_keys=True,
                allow_nan=False,
            )

            self.path.parent.mkdir(
                parents=True,
                exist_ok=True,
            )

            with self.path.open(
                "a",
                encoding="utf-8",
                newline="\n",
            ) as handle:
                handle.write(encoded + "\n")
                handle.flush()
                os.fsync(handle.fileno())

            self.last_appended_at = (
                record["recorded_at"]
            )

        return deepcopy(record)

    def all(
        self,
        *,
        limit: int | None = None,
        newest_first: bool = False,
    ) -> list[dict[str, Any]]:
        with self._lock:
            records = self._read_unlocked()

        if newest_first:
            records.reverse()

        if limit is not None:
            normalized_limit = max(
                0,
                int(limit),
            )
            records = records[:normalized_limit]

        return deepcopy(records)

    def count(self) -> int:
        with self._lock:
            return len(
                self._read_unlocked()
            )

    def verify_integrity(self) -> dict[str, Any]:
        with self._lock:
            records = self._read_unlocked()

        previous_hash: str | None = None
        errors: list[dict[str, Any]] = []

        for expected_sequence, record in enumerate(
            records,
            start=1,
        ):
            sequence = record.get("sequence")

            if sequence != expected_sequence:
                errors.append(
                    {
                        "sequence": expected_sequence,
                        "error": "INVALID_SEQUENCE",
                        "found": sequence,
                    }
                )

            if (
                record.get("schema_version")
                != self.SCHEMA_VERSION
            ):
                errors.append(
                    {
                        "sequence": expected_sequence,
                        "error": "INVALID_SCHEMA_VERSION",
                        "found": record.get(
                            "schema_version"
                        ),
                    }
                )

            if (
                record.get("previous_hash")
                != previous_hash
            ):
                errors.append(
                    {
                        "sequence": expected_sequence,
                        "error": "INVALID_PREVIOUS_HASH",
                    }
                )

            stored_hash = record.get(
                "record_hash"
            )

            material = dict(record)
            material.pop("record_hash", None)

            calculated_hash = (
                self._calculate_hash(material)
            )

            if stored_hash != calculated_hash:
                errors.append(
                    {
                        "sequence": expected_sequence,
                        "error": "INVALID_RECORD_HASH",
                    }
                )

            safety = record.get(
                "safety",
                {},
            )

            if not isinstance(safety, Mapping):
                errors.append(
                    {
                        "sequence": expected_sequence,
                        "error": "INVALID_SAFETY_BLOCK",
                    }
                )
            else:
                for flag in self.PROTECTED_FALSE_FLAGS:
                    if safety.get(flag) is not False:
                        errors.append(
                            {
                                "sequence": expected_sequence,
                                "error": (
                                    "UNSAFE_FLAG_VALUE"
                                ),
                                "flag": flag,
                            }
                        )

            previous_hash = (
                stored_hash
                if isinstance(stored_hash, str)
                else None
            )

        self.last_verified_at = _utc_now()

        return {
            "status": (
                "VALID"
                if not errors
                else "INVALID"
            ),
            "record_count": len(records),
            "errors": errors,
            "last_record_hash": previous_hash,
            "verified_at": self.last_verified_at,
            **deepcopy(self.SAFETY_FLAGS),
        }

    def status(self) -> dict[str, Any]:
        return {
            "status": "READY",
            "path": str(self.path),
            "exists": self.exists(),
            "format": "jsonl",
            "append_only": True,
            "hash_algorithm": "sha256",
            "hash_chain": True,
            "schema_version": self.SCHEMA_VERSION,
            "record_count": self.count(),
            "last_appended_at": self.last_appended_at,
            "last_verified_at": self.last_verified_at,
            **deepcopy(self.SAFETY_FLAGS),
        }


shadow_execution_audit_repository = (
    ShadowExecutionAuditRepository()
)
