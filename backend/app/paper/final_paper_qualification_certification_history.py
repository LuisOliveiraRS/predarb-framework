from __future__ import annotations

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


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


class FinalPaperQualificationCertificationHistory:
    """Histórico persistente da certificação técnica final Paper."""

    VALID_STATUSES = {
        "CERTIFIED",
        "PENDING",
        "BLOCKED",
        "NO_DATA",
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
                "PAPER_FINAL_QUALIFICATION_CERTIFICATION_HISTORY_PATH",
                (
                    "paper_data/"
                    "final_paper_qualification_certification_history.json"
                ),
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.max_entries = max(
            1,
            min(int(max_entries), 50000),
        )
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
        status = str(
            report.get("status") or ""
        ).upper()

        if status not in cls.VALID_STATUSES:
            raise ValueError(
                "Status da certificação técnica final inválido."
            )

        if (
            report.get("scope")
            != "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
        ):
            raise ValueError(
                "O relatório deve ter escopo "
                "PAPER_QUALIFICATION_CERTIFICATION_ONLY."
            )

        cls._validate_safety(
            "qualification_certification_report",
            report,
        )

        if not isinstance(
            report.get("checks"),
            list,
        ):
            raise ValueError(
                "Lista de checks da certificação inválida."
            )

        if not isinstance(
            report.get("failures"),
            list,
        ):
            raise ValueError(
                "Lista de falhas da certificação inválida."
            )

        if not isinstance(
            report.get("summary"),
            Mapping,
        ):
            raise ValueError(
                "Resumo da certificação inválido."
            )

        if not isinstance(
            report.get("criteria"),
            Mapping,
        ):
            raise ValueError(
                "Critérios da certificação inválidos."
            )

    @classmethod
    def _validate_entry(
        cls,
        entry: Mapping[str, Any],
    ) -> None:
        status = str(
            entry.get("status") or ""
        ).upper()

        if status not in cls.VALID_STATUSES:
            raise ValueError(
                "Status da entrada da certificação inválido."
            )

        if (
            entry.get("scope")
            != "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
        ):
            raise ValueError(
                "Escopo da entrada da certificação inválido."
            )

        if not entry.get("id"):
            raise ValueError(
                "Identificador da entrada ausente."
            )

        cls._validate_safety(
            "qualification_certification_history_entry",
            entry,
        )

    def load(self) -> dict[str, Any]:
        with self._lock:
            if not self.path.is_file():
                return self._empty_state()

            payload = json.loads(
                self.path.read_text(
                    encoding="utf-8"
                )
            )

            if not isinstance(payload, dict):
                raise ValueError(
                    "Arquivo do histórico da certificação inválido."
                )

            payload.setdefault("version", 1)
            payload.setdefault("created_at", None)
            payload.setdefault("updated_at", None)
            payload.setdefault("entries", [])

            if not isinstance(
                payload["entries"],
                list,
            ):
                raise ValueError(
                    "Lista do histórico da certificação inválida."
                )

            self._validate_safety(
                "qualification_certification_history_state",
                payload,
            )

            for entry in payload["entries"]:
                if not isinstance(entry, Mapping):
                    raise ValueError(
                        "Entrada do histórico da certificação inválida."
                    )

                self._validate_entry(entry)

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
        payload.update(self._safe_flags())

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
                    default=str,
                )
                file.flush()
                os.fsync(file.fileno())

            temp_path.replace(self.path)

        finally:
            temp_path.unlink(missing_ok=True)

    @classmethod
    def _compact_entry(
        cls,
        report: Mapping[str, Any],
        *,
        entry_id: str,
        captured_at: str,
    ) -> dict[str, Any]:
        summary = report.get("summary") or {}
        criteria = report.get("criteria") or {}

        failures = [
            item
            for item in (report.get("failures") or [])
            if isinstance(item, Mapping)
        ]

        return {
            "id": entry_id,
            "captured_at": captured_at,
            "report_generated_at": report.get(
                "generated_at"
            ),
            "status": str(
                report.get("status")
            ).upper(),
            "certified": (
                report.get("certified")
                is True
            ),
            "scope": (
                "PAPER_QUALIFICATION_CERTIFICATION_ONLY"
            ),
            "certification_score": round(
                _number(
                    report.get(
                        "certification_score"
                    )
                ),
                8,
            ),
            "criteria": {
                "min_gate_history_entries": _integer(
                    criteria.get(
                        "min_gate_history_entries"
                    )
                ),
                "min_qualified_streak": _integer(
                    criteria.get(
                        "min_qualified_streak"
                    )
                ),
                "min_current_gate_score": _number(
                    criteria.get(
                        "min_current_gate_score"
                    )
                ),
                "min_average_gate_score": _number(
                    criteria.get(
                        "min_average_gate_score"
                    )
                ),
                "max_gate_runtime_failures": _integer(
                    criteria.get(
                        "max_gate_runtime_failures"
                    )
                ),
            },
            "summary": {
                "total_checks": _integer(
                    summary.get(
                        "total_checks"
                    )
                ),
                "passed_checks": _integer(
                    summary.get(
                        "passed_checks"
                    )
                ),
                "failed_checks": _integer(
                    summary.get(
                        "failed_checks"
                    )
                ),
                "critical_failures": _integer(
                    summary.get(
                        "critical_failures"
                    )
                ),
                "warning_failures": _integer(
                    summary.get(
                        "warning_failures"
                    )
                ),
                "gate_status": (
                    summary.get(
                        "gate_status"
                    )
                ),
                "gate_score": _number(
                    summary.get(
                        "gate_score"
                    )
                ),
                "gate_history_entries": _integer(
                    summary.get(
                        "gate_history_entries"
                    )
                ),
                "latest_gate_status": (
                    summary.get(
                        "latest_gate_status"
                    )
                ),
                "latest_gate_score": _number(
                    summary.get(
                        "latest_gate_score"
                    )
                ),
                "average_gate_score": _number(
                    summary.get(
                        "average_gate_score"
                    )
                ),
                "current_streak_status": (
                    summary.get(
                        "current_streak_status"
                    )
                ),
                "current_streak": _integer(
                    summary.get(
                        "current_streak"
                    )
                ),
                "longest_qualified_streak": _integer(
                    summary.get(
                        "longest_qualified_streak"
                    )
                ),
                "gate_runtime_status": (
                    summary.get(
                        "gate_runtime_status"
                    )
                ),
                "gate_runtime_running": (
                    summary.get(
                        "gate_runtime_running"
                    )
                ),
                "gate_runtime_failures": _integer(
                    summary.get(
                        "gate_runtime_failures"
                    )
                ),
                "gate_critical_failures": _integer(
                    summary.get(
                        "gate_critical_failures"
                    )
                ),
            },
            "failure_codes": [
                str(
                    item.get("code")
                    or "UNKNOWN"
                )
                for item in failures
            ],
            **cls._safe_flags(),
        }

    def capture(
        self,
        report: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_report(report)

        with self._lock:
            state = self.load()
            captured_at = _utc_now()

            entry = self._compact_entry(
                report,
                entry_id=uuid.uuid4().hex,
                captured_at=captured_at,
            )

            entries = [
                dict(item)
                for item in (
                    state.get("entries")
                    or []
                )
                if isinstance(item, Mapping)
            ]

            entries.append(entry)

            if len(entries) > self.max_entries:
                entries = entries[
                    -self.max_entries:
                ]

            state.update(
                {
                    "created_at": (
                        state.get("created_at")
                        or captured_at
                    ),
                    "updated_at": captured_at,
                    "entries": entries,
                    **self._safe_flags(),
                }
            )

            self._save(state)

            return {
                "status": "captured",
                "entry": deepcopy(entry),
                "summary": self.summary(),
                **self._safe_flags(),
            }

    def list_entries(
        self,
        *,
        limit: int = 500,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 5000),
        )

        entries = [
            deepcopy(item)
            for item in (
                self.load().get(
                    "entries",
                    [],
                )
            )
            if isinstance(item, Mapping)
        ]

        entries.sort(
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
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
    def _current_streak(
        cls,
        entries: list[Mapping[str, Any]],
    ) -> tuple[str | None, int]:
        if not entries:
            return None, 0

        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        latest_status = str(
            ordered[-1].get(
                "status"
            )
            or ""
        ).upper()

        streak = 0

        for entry in reversed(ordered):
            if (
                str(
                    entry.get(
                        "status"
                    )
                    or ""
                ).upper()
                != latest_status
            ):
                break

            streak += 1

        return latest_status, streak

    @classmethod
    def _longest_certified_streak(
        cls,
        entries: list[Mapping[str, Any]],
    ) -> int:
        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        longest = 0
        current = 0

        for entry in ordered:
            if (
                str(
                    entry.get(
                        "status"
                    )
                    or ""
                ).upper()
                == "CERTIFIED"
            ):
                current += 1
                longest = max(longest, current)
            else:
                current = 0

        return longest

    @classmethod
    def _transition_count(
        cls,
        entries: list[Mapping[str, Any]],
    ) -> int:
        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        transitions = 0
        previous = None

        for entry in ordered:
            current = str(
                entry.get(
                    "status"
                )
                or ""
            ).upper()

            if (
                previous is not None
                and current != previous
            ):
                transitions += 1

            previous = current

        return transitions

    def summary(
        self,
    ) -> dict[str, Any]:
        state = self.load()

        entries = [
            item
            for item in (
                state.get(
                    "entries",
                    [],
                )
            )
            if isinstance(item, Mapping)
        ]

        status_counts = {
            status: sum(
                1
                for item in entries
                if (
                    str(
                        item.get(
                            "status"
                        )
                        or ""
                    ).upper()
                    == status
                )
            )
            for status in sorted(
                self.VALID_STATUSES
            )
        }

        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        latest = ordered[-1] if ordered else None

        scores = [
            _number(
                item.get(
                    "certification_score"
                )
            )
            for item in entries
        ]

        (
            current_streak_status,
            current_streak,
        ) = self._current_streak(entries)

        return {
            "status": "ok",
            "total_entries": len(entries),
            "status_counts": status_counts,
            "created_at": state.get("created_at"),
            "updated_at": state.get("updated_at"),
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
            "average_score": (
                round(
                    sum(scores)
                    / len(scores),
                    8,
                )
                if scores
                else None
            ),
            "best_score": (
                max(scores)
                if scores
                else None
            ),
            "worst_score": (
                min(scores)
                if scores
                else None
            ),
            "current_streak_status": (
                current_streak_status
            ),
            "current_streak": current_streak,
            "longest_certified_streak": (
                self._longest_certified_streak(
                    entries
                )
            ),
            "transitions": (
                self._transition_count(
                    entries
                )
            ),
            "history_path": str(self.path),
            **self._safe_flags(),
        }
