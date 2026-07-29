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


class FinalPaperValidationHistory:
    """Histórico persistente das avaliações finais do ambiente Paper."""

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
                "PAPER_FINAL_VALIDATION_HISTORY_PATH",
                "paper_data/"
                "final_paper_validation_history.json",
            )
        )

        candidate = Path(
            configured
        )

        if not candidate.is_absolute():
            candidate = (
                BACKEND_ROOT
                / candidate
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
            "next_step_authorized": False,
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

    @classmethod
    def _validate_safety(
        cls,
        name: str,
        payload: Mapping[str, Any],
    ) -> None:
        required_false = (
            "paper_execution_authorized",
            "live_authorization",
            "execution_authorized",
            "live_execution",
            "financial_execution",
            "next_step_authorized",
        )

        for field in required_false:
            if payload.get(
                field
            ) is not False:
                raise ValueError(
                    f"{name}: {field} não está "
                    "explicitamente bloqueado."
                )

        if payload.get(
            "read_only"
        ) is not True:
            raise ValueError(
                f"{name}: payload não está marcado "
                "como somente leitura."
            )

    @classmethod
    def _validate_entry(
        cls,
        entry: Mapping[str, Any],
    ) -> None:
        status = str(
            entry.get("status")
            or ""
        ).upper()

        if status not in (
            cls.VALID_STATUSES
        ):
            raise ValueError(
                "Status persistido da validação final inválido."
            )

        if (
            entry.get("scope")
            != "PAPER_VALIDATION_ONLY"
        ):
            raise ValueError(
                "Entrada persistida fora do escopo "
                "PAPER_VALIDATION_ONLY."
            )

        cls._validate_safety(
            "history_entry",
            entry,
        )

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
                "Arquivo do histórico da validação final inválido."
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
                "Lista do histórico da validação final inválida."
            )

        self._validate_safety(
            "history_state",
            payload,
        )

        for item in payload[
            "entries"
        ]:
            if not isinstance(
                item,
                Mapping,
            ):
                raise ValueError(
                    "Entrada inválida no histórico da validação final."
                )

            self._validate_entry(
                item
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
                "Status da validação final inválido."
            )

        if (
            report.get("scope")
            != "PAPER_VALIDATION_ONLY"
        ):
            raise ValueError(
                "O relatório deve ter escopo "
                "PAPER_VALIDATION_ONLY."
            )

        cls._validate_safety(
            "final_validation_report",
            report,
        )

        if not isinstance(
            report.get("checks"),
            list,
        ):
            raise ValueError(
                "Lista de checks da validação final inválida."
            )

        if not isinstance(
            report.get("failures"),
            list,
        ):
            raise ValueError(
                "Lista de falhas da validação final inválida."
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
            "validated": (
                report.get(
                    "validated"
                )
                is True
            ),
            "scope": (
                "PAPER_VALIDATION_ONLY"
            ),
            "validation_score": round(
                _number(
                    report.get(
                        "validation_score"
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
                "failed_validation_checks": _integer(
                    summary.get(
                        "failed_validation_checks"
                    )
                ),
                "assurance_status": (
                    summary.get(
                        "assurance_status"
                    )
                ),
                "assurance_score": _number(
                    summary.get(
                        "assurance_score"
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
                "gate_history_latest_status": (
                    summary.get(
                        "gate_history_latest_status"
                    )
                ),
                "qualified_streak": _integer(
                    summary.get(
                        "qualified_streak"
                    )
                ),
                "assurance_runtime_status": (
                    summary.get(
                        "assurance_runtime_status"
                    )
                ),
                "gate_runtime_status": (
                    summary.get(
                        "gate_runtime_status"
                    )
                ),
                "assurance_runtime_failures": _integer(
                    summary.get(
                        "assurance_runtime_failures"
                    )
                ),
                "gate_runtime_failures": _integer(
                    summary.get(
                        "gate_runtime_failures"
                    )
                ),
                "total_runtime_failures": _integer(
                    summary.get(
                        "total_runtime_failures"
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

        longest_validated = 0
        running_validated = 0

        for entry in ordered:
            if (
                entry.get("status")
                == "PAPER_VALIDATED"
            ):
                running_validated += 1
                longest_validated = max(
                    longest_validated,
                    running_validated,
                )
            else:
                running_validated = 0

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
            longest_validated,
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
                    "validation_score"
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
            longest_validated_streak,
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
            "status_counts": counts,
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
                        "validation_score"
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
            "longest_validated_streak": (
                longest_validated_streak
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

        result[
            "history_path"
        ] = str(
            self.path
        )

        return result
