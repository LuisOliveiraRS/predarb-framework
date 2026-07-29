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


class PaperAssuranceQualificationHistory:
    """Histórico persistente das avaliações do gate de qualificação."""

    VALID_STATUSES = {
        "QUALIFIED",
        "NOT_QUALIFIED",
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
                "PAPER_ASSURANCE_GATE_HISTORY_PATH",
                "paper_data/"
                "paper_assurance_qualification_history.json",
            )
        )

        candidate = Path(
            configured
        )

        if not candidate.is_absolute():
            candidate = (
                BACKEND_ROOT / candidate
            )

        self.path = (
            candidate.resolve()
        )

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

    def load(
        self,
    ) -> dict[str, Any]:
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
                "Arquivo de histórico do gate inválido."
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
                "Lista de avaliações do gate inválida."
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
            dir=str(
                self.path.parent
            ),
        )

        temp_path = Path(
            temp_name
        )

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
    def _validate_report(
        cls,
        report: Mapping[str, Any],
    ) -> None:
        status = str(
            report.get("status")
            or ""
        ).upper()

        if status not in (
            cls.VALID_STATUSES
        ):
            raise ValueError(
                "Status do gate inválido."
            )

        if (
            report.get("scope")
            != "PAPER_ASSURANCE_ONLY"
        ):
            raise ValueError(
                "O relatório deve ter escopo "
                "PAPER_ASSURANCE_ONLY."
            )

        required_false = (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
        )

        for field in required_false:
            if report.get(
                field
            ) is not False:
                raise ValueError(
                    f"{field} não está "
                    "explicitamente bloqueado."
                )

        if report.get(
            "read_only"
        ) is not True:
            raise ValueError(
                "Relatório não está marcado "
                "como somente leitura."
            )

        if not isinstance(
            report.get("checks"),
            list,
        ):
            raise ValueError(
                "Lista de checks do gate inválida."
            )

        if not isinstance(
            report.get("failures"),
            list,
        ):
            raise ValueError(
                "Lista de falhas do gate inválida."
            )

    @classmethod
    def _compact_entry(
        cls,
        report: Mapping[str, Any],
        *,
        captured_at: str,
    ) -> dict[str, Any]:
        summary = (
            report.get("summary")
            or {}
        )

        thresholds = (
            report.get("thresholds")
            or {}
        )

        failures = [
            item
            for item in (
                report.get("failures")
                or []
            )
            if isinstance(
                item,
                Mapping,
            )
        ]

        return {
            "id": uuid.uuid4().hex,
            "captured_at": captured_at,
            "report_generated_at": (
                report.get(
                    "generated_at"
                )
            ),
            "status": str(
                report.get("status")
            ).upper(),
            "qualified": (
                report.get("qualified")
                is True
            ),
            "scope": (
                "PAPER_ASSURANCE_ONLY"
            ),
            "qualification_score": round(
                _number(
                    report.get(
                        "qualification_score"
                    )
                ),
                8,
            ),
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
                "failed_data_checks": _integer(
                    summary.get(
                        "failed_data_checks"
                    )
                ),
                "failed_qualification_checks": _integer(
                    summary.get(
                        "failed_qualification_checks"
                    )
                ),
                "total_history_entries": _integer(
                    summary.get(
                        "total_history_entries"
                    )
                ),
                "recent_entries": _integer(
                    summary.get(
                        "recent_entries"
                    )
                ),
                "latest_status": (
                    summary.get(
                        "latest_status"
                    )
                ),
                "latest_score": _number(
                    summary.get(
                        "latest_score"
                    )
                ),
                "recent_average_score": _number(
                    summary.get(
                        "recent_average_score"
                    )
                ),
                "assured_streak": _integer(
                    summary.get(
                        "assured_streak"
                    )
                ),
                "recent_warning": _integer(
                    summary.get(
                        "recent_warning"
                    )
                ),
                "recent_blocked": _integer(
                    summary.get(
                        "recent_blocked"
                    )
                ),
                "recent_critical": _integer(
                    summary.get(
                        "recent_critical"
                    )
                ),
            },
            "thresholds": deepcopy(
                dict(thresholds)
            ),
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
        self._validate_report(
            report
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
            report,
            captured_at=captured_at,
        )

        entries.append(
            entry
        )

        entries = entries[
            -self.max_entries:
        ]

        state.update(
            {
                "updated_at": (
                    captured_at
                ),
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
    ) -> tuple[
        int,
        int,
        str | None,
    ]:
        if not entries:
            return (
                0,
                0,
                None,
            )

        ordered = sorted(
            entries,
            key=lambda item: str(
                item.get(
                    "captured_at"
                )
                or ""
            ),
        )

        longest_qualified = 0
        running_qualified = 0

        for entry in ordered:
            if (
                entry.get("status")
                == "QUALIFIED"
            ):
                running_qualified += 1
                longest_qualified = max(
                    longest_qualified,
                    running_qualified,
                )
            else:
                running_qualified = 0

        latest_status = ordered[
            -1
        ].get("status")

        current_streak = 0

        for entry in reversed(
            ordered
        ):
            if (
                entry.get("status")
                == latest_status
            ):
                current_streak += 1
            else:
                break

        return (
            current_streak,
            longest_qualified,
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
                    "qualification_score"
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
            longest_qualified_streak,
            current_streak_status,
        ) = cls._streaks(
            entries
        )

        return {
            "status": "ok",
            "updated_at": (
                state.get(
                    "updated_at"
                )
            ),
            "total_entries": len(
                entries
            ),
            "status_counts": (
                counts
            ),
            "latest_status": (
                latest.get(
                    "status"
                )
                if latest
                else None
            ),
            "latest_score": (
                _number(
                    latest.get(
                        "qualification_score"
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
                current_streak_status
            ),
            "longest_qualified_streak": (
                longest_qualified_streak
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

        result = (
            self._summary_from_state(
                state
            )
        )

        result["history_path"] = str(
            self.path
        )

        return result
