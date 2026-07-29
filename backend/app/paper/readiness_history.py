from __future__ import annotations

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


class PaperReadinessHistory:
    """Histórico persistente das avaliações do Readiness Gate."""

    VALID_STATUSES = {
        "READY",
        "NOT_READY",
        "INSUFFICIENT_DATA",
    }

    def __init__(
        self,
        path: str | Path | None = None,
        *,
        max_entries: int = 1000,
    ) -> None:
        configured = (
            path
            if path is not None
            else os.getenv(
                "PAPER_READINESS_HISTORY_PATH",
                "paper_data/paper_readiness_history.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.path = candidate.resolve()
        self.max_entries = max(
            10,
            min(int(max_entries), 10000),
        )

    @staticmethod
    def _empty_state() -> dict[str, Any]:
        return {
            "version": 1,
            "updated_at": None,
            "entries": [],
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
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
                "Arquivo de histórico inválido."
            )

        payload.setdefault("version", 1)
        payload.setdefault("updated_at", None)
        payload.setdefault("entries", [])

        if not isinstance(
            payload["entries"],
            list,
        ):
            raise ValueError(
                "Lista de avaliações inválida."
            )

        payload["execution_authorized"] = False
        payload["live_execution"] = False
        payload["financial_execution"] = False

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

            temp_path.replace(
                self.path
            )

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
                "Status de readiness inválido."
            )

        if report.get(
            "execution_authorized"
        ) is not False:
            raise ValueError(
                "Execução não está explicitamente bloqueada."
            )

        if report.get(
            "live_execution"
        ) is not False:
            raise ValueError(
                "Execução live não está explicitamente bloqueada."
            )

        if report.get(
            "financial_execution"
        ) is not False:
            raise ValueError(
                "Execução financeira não está explicitamente bloqueada."
            )

        if report.get("read_only") is not True:
            raise ValueError(
                "Relatório não está marcado como somente leitura."
            )

    @staticmethod
    def _compact_entry(
        report: Mapping[str, Any],
        previous: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        summary = report.get("summary") or {}
        score = _number(
            report.get("readiness_score")
        )

        previous_score = (
            _number(
                previous.get(
                    "readiness_score"
                )
            )
            if previous
            else None
        )

        return {
            "id": uuid.uuid4().hex,
            "captured_at": _utc_now(),
            "report_generated_at": report.get(
                "generated_at"
            ),
            "status": str(
                report.get("status")
            ).upper(),
            "ready": bool(
                report.get("ready")
            ),
            "readiness_score": score,
            "score_delta": (
                round(
                    score - previous_score,
                    8,
                )
                if previous_score is not None
                else None
            ),
            "operations_status": report.get(
                "operations_status"
            ),
            "passed_checks": _integer(
                summary.get(
                    "passed_checks"
                )
            ),
            "blockers": _integer(
                summary.get("blockers")
            ),
            "warnings": _integer(
                summary.get("warnings")
            ),
            "insufficient_data": _integer(
                summary.get(
                    "insufficient_data"
                )
            ),
            "thresholds": deepcopy(
                report.get("thresholds") or {}
            ),
            "blocker_codes": [
                str(item.get("code"))
                for item in (
                    report.get("blockers")
                    or []
                )
                if isinstance(item, Mapping)
                and item.get("code")
            ],
            "warning_codes": [
                str(item.get("code"))
                for item in (
                    report.get("warnings")
                    or []
                )
                if isinstance(item, Mapping)
                and item.get("code")
            ],
            "insufficient_codes": [
                str(item.get("code"))
                for item in (
                    report.get(
                        "insufficient_data"
                    )
                    or []
                )
                if isinstance(item, Mapping)
                and item.get("code")
            ],
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

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

        previous = (
            entries[-1]
            if entries
            else None
        )

        entry = self._compact_entry(
            report,
            previous,
        )

        entries.append(entry)
        entries = entries[
            -self.max_entries:
        ]

        now = _utc_now()

        state.update(
            {
                "updated_at": now,
                "entries": entries,
                "execution_authorized": False,
                "live_execution": False,
                "financial_execution": False,
            }
        )

        self._save(state)

        return {
            "status": "captured",
            "entry": deepcopy(entry),
            "summary": self._summary_from_entries(
                entries,
                updated_at=now,
            ),
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    def list_entries(
        self,
        *,
        limit: int = 100,
        status: str | None = None,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 5000),
        )

        normalized_status = (
            str(status).strip().upper()
            if status
            else None
        )

        if (
            normalized_status is not None
            and normalized_status
            not in self.VALID_STATUSES
        ):
            raise ValueError(
                "Filtro de status inválido."
            )

        entries = [
            deepcopy(item)
            for item in self.load().get(
                "entries",
                [],
            )
            if isinstance(item, Mapping)
        ]

        if normalized_status:
            entries = [
                item
                for item in entries
                if item.get("status")
                == normalized_status
            ]

        entries.sort(
            key=lambda item: str(
                item.get("captured_at")
                or ""
            ),
            reverse=True,
        )

        return entries[
            :normalized_limit
        ]

    def latest(
        self,
    ) -> dict[str, Any] | None:
        entries = self.list_entries(
            limit=1
        )

        return (
            entries[0]
            if entries
            else None
        )

    @staticmethod
    def _streaks(
        entries: list[Mapping[str, Any]],
    ) -> dict[str, Any]:
        if not entries:
            return {
                "current_status": None,
                "current_streak": 0,
                "longest_ready_streak": 0,
                "status_transitions": 0,
            }

        current_status = str(
            entries[-1].get("status")
        )

        current_streak = 0

        for item in reversed(entries):
            if (
                str(item.get("status"))
                == current_status
            ):
                current_streak += 1
            else:
                break

        longest_ready = 0
        running_ready = 0
        transitions = 0
        previous_status = None

        for item in entries:
            status = str(
                item.get("status")
            )

            if (
                previous_status is not None
                and status != previous_status
            ):
                transitions += 1

            previous_status = status

            if status == "READY":
                running_ready += 1
                longest_ready = max(
                    longest_ready,
                    running_ready,
                )
            else:
                running_ready = 0

        return {
            "current_status": current_status,
            "current_streak": current_streak,
            "longest_ready_streak": longest_ready,
            "status_transitions": transitions,
        }

    @classmethod
    def _summary_from_entries(
        cls,
        entries: list[Mapping[str, Any]],
        *,
        updated_at: str | None,
    ) -> dict[str, Any]:
        ready_entries = [
            item
            for item in entries
            if item.get("status")
            == "READY"
        ]

        not_ready_entries = [
            item
            for item in entries
            if item.get("status")
            == "NOT_READY"
        ]

        insufficient_entries = [
            item
            for item in entries
            if item.get("status")
            == "INSUFFICIENT_DATA"
        ]

        scores = [
            _number(
                item.get(
                    "readiness_score"
                )
            )
            for item in entries
        ]

        latest = (
            entries[-1]
            if entries
            else None
        )

        return {
            "status": "ok",
            "updated_at": updated_at,
            "total_entries": len(entries),
            "ready_entries": len(
                ready_entries
            ),
            "not_ready_entries": len(
                not_ready_entries
            ),
            "insufficient_data_entries": len(
                insufficient_entries
            ),
            "latest_status": (
                latest.get("status")
                if latest
                else None
            ),
            "latest_score": (
                _number(
                    latest.get(
                        "readiness_score"
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
                else 0.0
            ),
            "best_score": (
                max(scores)
                if scores
                else 0.0
            ),
            "worst_score": (
                min(scores)
                if scores
                else 0.0
            ),
            **cls._streaks(entries),
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    def summary(
        self,
    ) -> dict[str, Any]:
        state = self.load()

        result = self._summary_from_entries(
            [
                item
                for item in state.get(
                    "entries",
                    [],
                )
                if isinstance(
                    item,
                    Mapping,
                )
            ],
            updated_at=state.get(
                "updated_at"
            ),
        )

        result["history_path"] = str(
            self.path
        )

        return result
