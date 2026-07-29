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


class PaperCertificationAssuranceHistory:
    """Histórico persistente dos snapshots do Centro de Garantia Paper."""

    VALID_STATUSES = {
        "ASSURED",
        "WARNING",
        "PENDING",
        "BLOCKED",
        "CRITICAL",
        "UNKNOWN",
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
                "PAPER_ASSURANCE_HISTORY_PATH",
                "paper_data/"
                "paper_certification_assurance_history.json",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = (
                BACKEND_ROOT / candidate
            )

        self.path = candidate.resolve()
        self.max_entries = max(
            10,
            min(
                int(max_entries),
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
            "entries": [],
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

        if not isinstance(
            payload,
            dict,
        ):
            raise ValueError(
                "Arquivo de histórico de garantia inválido."
            )

        payload.setdefault(
            "version",
            1,
        )
        payload.setdefault(
            "updated_at",
            None,
        )
        payload.setdefault(
            "entries",
            [],
        )

        if not isinstance(
            payload["entries"],
            list,
        ):
            raise ValueError(
                "Lista de histórico de garantia inválida."
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

    @classmethod
    def _validate_snapshot(
        cls,
        snapshot: Mapping[str, Any],
    ) -> None:
        status = str(
            snapshot.get("status")
            or ""
        ).upper()

        if status not in (
            cls.VALID_STATUSES
        ):
            raise ValueError(
                "Status de garantia inválido."
            )

        if (
            snapshot.get("scope")
            != "PAPER_ONLY"
        ):
            raise ValueError(
                "O snapshot deve ter escopo PAPER_ONLY."
            )

        required_false = (
            "paper_execution_authorized",
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
                    f"{field} não está explicitamente bloqueado."
                )

        if snapshot.get(
            "read_only"
        ) is not True:
            raise ValueError(
                "Snapshot não está marcado como somente leitura."
            )

    @classmethod
    def _compact_entry(
        cls,
        snapshot: Mapping[str, Any],
        *,
        captured_at: str,
    ) -> dict[str, Any]:
        summary = (
            snapshot.get("summary")
            or {}
        )

        return {
            "id": uuid.uuid4().hex,
            "captured_at": captured_at,
            "snapshot_generated_at": (
                snapshot.get(
                    "generated_at"
                )
            ),
            "status": str(
                snapshot.get("status")
            ).upper(),
            "assured": bool(
                snapshot.get("assured")
            ),
            "scope": "PAPER_ONLY",
            "assurance_score": round(
                _number(
                    snapshot.get(
                        "assurance_score"
                    )
                ),
                8,
            ),
            "summary": {
                "certification_status": (
                    summary.get(
                        "certification_status"
                    )
                ),
                "certification_score": (
                    _number(
                        summary.get(
                            "certification_score"
                        )
                    )
                ),
                "monitor_status": (
                    summary.get(
                        "monitor_status"
                    )
                ),
                "monitor_score": (
                    _number(
                        summary.get(
                            "monitor_score"
                        )
                    )
                ),
                "chain_status": (
                    summary.get(
                        "chain_status"
                    )
                ),
                "chain_valid": (
                    summary.get(
                        "chain_valid"
                    )
                    is True
                ),
                "evidence_entries": (
                    _integer(
                        summary.get(
                            "evidence_entries"
                        )
                    )
                ),
                "active_incidents": (
                    _integer(
                        summary.get(
                            "active_incidents"
                        )
                    )
                ),
                "active_critical": (
                    _integer(
                        summary.get(
                            "active_critical"
                        )
                    )
                ),
                "active_warning": (
                    _integer(
                        summary.get(
                            "active_warning"
                        )
                    )
                ),
                "runtime_status": (
                    summary.get(
                        "runtime_status"
                    )
                ),
                "runtime_cycles": (
                    _integer(
                        summary.get(
                            "runtime_cycles"
                        )
                    )
                ),
                "runtime_failures": (
                    _integer(
                        summary.get(
                            "runtime_failures"
                        )
                    )
                ),
            },
            **cls._safe_flags(),
        }

    def capture(
        self,
        snapshot: Mapping[str, Any],
    ) -> dict[str, Any]:
        self._validate_snapshot(
            snapshot
        )

        state = self.load()
        captured_at = _utc_now()

        entries = [
            dict(item)
            for item in state.get(
                "entries",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        entry = self._compact_entry(
            snapshot,
            captured_at=captured_at,
        )

        entries.append(entry)
        entries = entries[
            -self.max_entries:
        ]

        state.update(
            {
                "updated_at": captured_at,
                "entries": entries,
                **self._safe_flags(),
            }
        )

        self._save(
            state
        )

        return {
            "status": "captured",
            "entry": deepcopy(
                entry
            ),
            "summary": (
                self._summary_from_state(
                    state
                )
            ),
            **self._safe_flags(),
        }

    def list_entries(
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

        entries = [
            deepcopy(item)
            for item in self.load().get(
                "entries",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
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

    @classmethod
    def _streaks(
        cls,
        entries: list[
            Mapping[str, Any]
        ],
    ) -> tuple[int, int, str | None]:
        if not entries:
            return 0, 0, None

        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        longest_assured = 0
        running_assured = 0

        for entry in ordered:
            if entry.get(
                "status"
            ) == "ASSURED":
                running_assured += 1
                longest_assured = max(
                    longest_assured,
                    running_assured,
                )
            else:
                running_assured = 0

        latest_status = ordered[-1].get(
            "status"
        )

        current_streak = 0

        for entry in reversed(
            ordered
        ):
            if entry.get(
                "status"
            ) == latest_status:
                current_streak += 1
            else:
                break

        return (
            current_streak,
            longest_assured,
            (
                str(latest_status)
                if latest_status
                else None
            ),
        )

    @classmethod
    def _transition_count(
        cls,
        entries: list[
            Mapping[str, Any]
        ],
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
            status = entry.get(
                "status"
            )

            if (
                previous is not None
                and status != previous
            ):
                transitions += 1

            previous = status

        return transitions

    @classmethod
    def _summary_from_state(
        cls,
        state: Mapping[str, Any],
    ) -> dict[str, Any]:
        entries = [
            item
            for item in state.get(
                "entries",
                [],
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        counts = {
            status: sum(
                1
                for item in entries
                if item.get(
                    "status"
                ) == status
            )
            for status in (
                cls.VALID_STATUSES
            )
        }

        scores = [
            _number(
                item.get(
                    "assurance_score"
                )
            )
            for item in entries
        ]

        latest = (
            max(
                entries,
                key=lambda item: str(
                    item.get(
                        "captured_at"
                    )
                    or ""
                ),
            )
            if entries
            else None
        )

        (
            current_streak,
            longest_assured_streak,
            streak_status,
        ) = cls._streaks(
            entries
        )

        return {
            "status": "ok",
            "updated_at": state.get(
                "updated_at"
            ),
            "total_entries": len(
                entries
            ),
            "status_counts": counts,
            "latest_status": (
                latest.get("status")
                if latest
                else None
            ),
            "latest_score": (
                _number(
                    latest.get(
                        "assurance_score"
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
            "current_streak": (
                current_streak
            ),
            "current_streak_status": (
                streak_status
            ),
            "longest_assured_streak": (
                longest_assured_streak
            ),
            "transitions": (
                cls._transition_count(
                    entries
                )
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
        result["history_path"] = str(
            self.path
        )

        return result
