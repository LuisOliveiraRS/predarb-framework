from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping
from copy import deepcopy
from threading import RLock
from typing import Any


class ExecutionHistory:
    """Histórico thread-safe de execuções agrupadas por venue.

    O histórico armazena relatórios reais já produzidos pelo OMS. Planejamento
    de rota não é registrado como execução e, portanto, não alimenta o modelo.
    """

    def __init__(self) -> None:
        self._history: dict[str, list[Any]] = defaultdict(list)
        self._display_names: dict[str, str] = {}
        self._lock = RLock()

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @classmethod
    def _infer_venue(cls, report: Any) -> str:
        for field_name in ("venue", "exchange", "platform"):
            value = cls._read(report, field_name, None)
            if value:
                return str(value).strip()

        order = cls._read(report, "order", None)
        value = cls._read(order, "platform", None)
        if value:
            return str(value).strip()

        result = cls._read(report, "result", None)
        for field_name in ("venue", "exchange", "platform"):
            value = cls._read(result, field_name, None)
            if value:
                return str(value).strip()

        return ""

    @staticmethod
    def _copy(value: Any) -> Any:
        try:
            return deepcopy(value)
        except Exception:
            return value

    @staticmethod
    def _key(venue: Any) -> tuple[str, str]:
        display = str(venue or "").strip()
        if not display:
            raise ValueError("venue é obrigatória para registrar uma execução.")
        return display.casefold(), display

    def add(self, venue: Any, report: Any | None = None) -> Any:
        """Registra um relatório.

        Formas aceitas:

            history.add("Exchange A", report)
            history.add(report)  # venue inferida do relatório
        """

        if report is None:
            report = venue
            venue = self._infer_venue(report)

        if report is None:
            raise ValueError("report não pode ser None.")

        key, display = self._key(venue)
        stored = self._copy(report)

        with self._lock:
            self._display_names.setdefault(key, display)
            self._history[key].append(stored)

        return report

    record = add

    def add_many(self, venue: Any, reports: Any) -> int:
        if isinstance(reports, (str, bytes, Mapping)):
            reports = [reports]
        count = 0
        for report in reports:
            self.add(venue, report)
            count += 1
        return count

    def get(self, venue: Any) -> list[Any]:
        key, _ = self._key(venue)
        with self._lock:
            return [self._copy(item) for item in self._history.get(key, [])]

    def latest(self, venue: Any) -> Any | None:
        reports = self.get(venue)
        return reports[-1] if reports else None

    def all(self) -> dict[str, list[Any]]:
        with self._lock:
            return {
                self._display_names.get(key, key): [
                    self._copy(item) for item in reports
                ]
                for key, reports in self._history.items()
            }

    snapshot = all

    def venues(self) -> list[str]:
        with self._lock:
            return sorted(self._display_names.values(), key=str.casefold)

    def count(self, venue: Any | None = None) -> int:
        if venue is None:
            return self.total_reports()
        key, _ = self._key(venue)
        with self._lock:
            return len(self._history.get(key, []))

    def total_reports(self) -> int:
        with self._lock:
            return sum(len(reports) for reports in self._history.values())

    def clear(self, venue: Any | None = None) -> None:
        with self._lock:
            if venue is None:
                self._history.clear()
                self._display_names.clear()
                return

            key, _ = self._key(venue)
            self._history.pop(key, None)
            self._display_names.pop(key, None)

    reset = clear

    def status(self) -> dict[str, Any]:
        return {
            "venues": len(self.venues()),
            "reports": self.total_reports(),
            "reports_by_venue": {
                venue: self.count(venue) for venue in self.venues()
            },
            "live_execution": False,
        }


execution_history = ExecutionHistory()
