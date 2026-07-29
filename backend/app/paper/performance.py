from __future__ import annotations

import csv
import json
import os
import re
from pathlib import Path
from statistics import mean
from typing import Any, Iterable, Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORT_NAME_PATTERN = re.compile(
    r"^phase8_long_session_[A-Za-z0-9_.-]+\.json$"
)


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


def _boolean(value: Any) -> bool | None:
    if isinstance(value, bool):
        return value

    if value is None:
        return None

    normalized = str(value).strip().lower()

    if normalized in {"true", "1", "yes", "sim"}:
        return True

    if normalized in {"false", "0", "no", "nao", "não"}:
        return False

    return None


def _read_json(path: Path) -> dict[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise ValueError(
            f"Relatório inválido: {path.name}"
        )

    return payload


class PaperPerformanceService:
    """Leitura consolidada dos relatórios Paper da Fase 8."""

    def __init__(
        self,
        reports_dir: str | Path | None = None,
    ) -> None:
        configured = (
            reports_dir
            if reports_dir is not None
            else os.getenv(
                "REAL_TEST_REPORTS_DIR",
                "real_test_reports",
            )
        )

        candidate = Path(configured)

        if not candidate.is_absolute():
            candidate = BACKEND_ROOT / candidate

        self.reports_dir = candidate.resolve()

    def _report_paths(self) -> list[Path]:
        if not self.reports_dir.exists():
            return []

        return sorted(
            self.reports_dir.glob(
                "phase8_long_session_*.json"
            ),
            key=lambda item: item.stat().st_mtime,
            reverse=True,
        )

    @staticmethod
    def _report_record(
        path: Path,
        payload: Mapping[str, Any],
    ) -> dict[str, Any]:
        summary = payload.get("summary") or {}
        performance = payload.get("performance") or {}

        return {
            "name": path.name,
            "label": payload.get("label") or "",
            "status": summary.get("status") or "UNKNOWN",
            "started_at": payload.get("started_at"),
            "finished_at": payload.get("finished_at"),
            "actual_duration_seconds": _number(
                payload.get("actual_duration_seconds")
            ),
            "samples": _integer(
                summary.get("samples")
            ),
            "cycles": _integer(
                performance.get("cycles_delta")
            ),
            "successful_cycles": _integer(
                performance.get(
                    "successful_cycles_delta"
                )
            ),
            "failed_cycles": _integer(
                performance.get(
                    "failed_cycles_delta"
                )
            ),
            "no_signal_cycles": _integer(
                performance.get(
                    "no_signal_cycles_delta"
                )
            ),
            "risk_stopped_cycles": _integer(
                performance.get(
                    "risk_stopped_cycles_delta"
                )
            ),
            "trades": _integer(
                performance.get("trade_count_delta")
            ),
            "start_equity": _number(
                performance.get("start_equity")
            ),
            "end_equity": _number(
                performance.get("end_equity")
            ),
            "equity_delta": _number(
                performance.get("equity_delta")
            ),
            "session_return_rate": _number(
                performance.get(
                    "session_return_rate"
                )
            ),
            "max_drawdown": _number(
                performance.get("max_drawdown")
            ),
            "max_drawdown_rate": _number(
                performance.get(
                    "max_drawdown_rate"
                )
            ),
            "endpoint_errors": _integer(
                summary.get("endpoint_errors")
            ),
            "safety_violations": _integer(
                summary.get("safety_violations")
            ),
        }

    def list_reports(
        self,
        *,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 500),
        )

        records: list[dict[str, Any]] = []

        for path in self._report_paths()[
            :normalized_limit
        ]:
            try:
                payload = _read_json(path)
                records.append(
                    self._report_record(
                        path,
                        payload,
                    )
                )
            except (
                OSError,
                ValueError,
                json.JSONDecodeError,
            ) as exc:
                records.append(
                    {
                        "name": path.name,
                        "status": "INVALID",
                        "error": str(exc),
                    }
                )

        return records

    def summary(self) -> dict[str, Any]:
        records = [
            item
            for item in self.list_reports(limit=500)
            if item.get("status") != "INVALID"
        ]

        returns = [
            _number(
                item.get("session_return_rate")
            )
            for item in records
        ]

        latest = records[0] if records else None

        return {
            "status": "ok",
            "reports_dir": str(self.reports_dir),
            "total_reports": len(records),
            "passed_reports": sum(
                1
                for item in records
                if item.get("status") == "PASS"
            ),
            "failed_reports": sum(
                1
                for item in records
                if item.get("status") == "FAIL"
            ),
            "total_cycles": sum(
                _integer(item.get("cycles"))
                for item in records
            ),
            "successful_cycles": sum(
                _integer(
                    item.get("successful_cycles")
                )
                for item in records
            ),
            "failed_cycles": sum(
                _integer(
                    item.get("failed_cycles")
                )
                for item in records
            ),
            "no_signal_cycles": sum(
                _integer(
                    item.get("no_signal_cycles")
                )
                for item in records
            ),
            "risk_stopped_cycles": sum(
                _integer(
                    item.get("risk_stopped_cycles")
                )
                for item in records
            ),
            "total_trades": sum(
                _integer(item.get("trades"))
                for item in records
            ),
            "cumulative_equity_delta": round(
                sum(
                    _number(
                        item.get("equity_delta")
                    )
                    for item in records
                ),
                8,
            ),
            "average_session_return_rate": round(
                mean(returns)
                if returns
                else 0.0,
                8,
            ),
            "best_session_return_rate": round(
                max(returns)
                if returns
                else 0.0,
                8,
            ),
            "worst_session_return_rate": round(
                min(returns)
                if returns
                else 0.0,
                8,
            ),
            "max_drawdown_rate": round(
                max(
                    (
                        _number(
                            item.get(
                                "max_drawdown_rate"
                            )
                        )
                        for item in records
                    ),
                    default=0.0,
                ),
                8,
            ),
            "endpoint_errors": sum(
                _integer(
                    item.get("endpoint_errors")
                )
                for item in records
            ),
            "safety_violations": sum(
                _integer(
                    item.get("safety_violations")
                )
                for item in records
            ),
            "latest_report": (
                latest.get("name")
                if latest
                else None
            ),
            "latest_finished_at": (
                latest.get("finished_at")
                if latest
                else None
            ),
            "execution_authorized": False,
            "live_execution": False,
        }

    def _validated_report_path(
        self,
        report_name: str,
    ) -> Path:
        if (
            not report_name
            or Path(report_name).name != report_name
            or not REPORT_NAME_PATTERN.fullmatch(
                report_name
            )
        ):
            raise ValueError(
                "Nome de relatório inválido."
            )

        path = (
            self.reports_dir
            / report_name
        ).resolve()

        if path.parent != self.reports_dir:
            raise ValueError(
                "Caminho de relatório inválido."
            )

        return path

    def get_report(
        self,
        report_name: str,
    ) -> dict[str, Any]:
        path = self._validated_report_path(
            report_name
        )

        if not path.is_file():
            raise FileNotFoundError(
                report_name
            )

        return _read_json(path)

    @staticmethod
    def _convert_history_row(
        row: Mapping[str, Any],
    ) -> dict[str, Any]:
        numeric_fields = {
            "total_cycles",
            "successful_cycles",
            "failed_cycles",
            "no_signal_cycles",
            "risk_stopped_cycles",
            "equity",
            "total_pnl",
            "realized_pnl",
            "unrealized_pnl",
            "return_rate",
            "trade_count",
            "open_positions",
            "max_drawdown",
            "max_drawdown_rate",
            "latency_session_ms",
            "latency_account_ms",
        }

        boolean_fields = {
            "runtime_running",
            "risk_approved",
        }

        converted: dict[str, Any] = dict(row)

        for field in numeric_fields:
            if field in converted:
                converted[field] = _number(
                    converted[field]
                )

        for field in boolean_fields:
            if field in converted:
                converted[field] = _boolean(
                    converted[field]
                )

        return converted

    def history(
        self,
        *,
        limit: int = 500,
        report_limit: int = 20,
    ) -> list[dict[str, Any]]:
        normalized_limit = max(
            1,
            min(int(limit), 5000),
        )

        normalized_report_limit = max(
            1,
            min(int(report_limit), 200),
        )

        points: list[dict[str, Any]] = []

        for report in reversed(
            self.list_reports(
                limit=normalized_report_limit
            )
        ):
            report_name = report.get("name")

            if not report_name:
                continue

            report_path = (
                self.reports_dir
                / report_name
            )

            csv_path = report_path.with_suffix(
                ".csv"
            )

            if csv_path.is_file():
                with csv_path.open(
                    "r",
                    encoding="utf-8-sig",
                    newline="",
                ) as file:
                    for row in csv.DictReader(file):
                        point = (
                            self._convert_history_row(
                                row
                            )
                        )
                        point["report_name"] = (
                            report_name
                        )
                        point["label"] = (
                            report.get("label")
                            or ""
                        )
                        points.append(point)

                continue

            try:
                payload = self.get_report(
                    report_name
                )
            except (
                OSError,
                ValueError,
                json.JSONDecodeError,
            ):
                continue

            for key in (
                "initial_sample",
                "final_sample",
            ):
                sample = payload.get(key)

                if not isinstance(
                    sample,
                    Mapping,
                ):
                    continue

                point = self._convert_history_row(
                    sample
                )
                point["report_name"] = (
                    report_name
                )
                point["label"] = (
                    report.get("label")
                    or ""
                )
                point["sample_type"] = key
                points.append(point)

        points.sort(
            key=lambda item: str(
                item.get("captured_at") or ""
            )
        )

        return points[-normalized_limit:]
