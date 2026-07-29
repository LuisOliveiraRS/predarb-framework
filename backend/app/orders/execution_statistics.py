from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from copy import deepcopy
from math import isfinite
from statistics import mean
from threading import RLock
from typing import Any


class ExecutionStatistics:
    """Agrega métricas dos relatórios de execução do OMS.

    Mantém as chaves legadas ``orders``, ``quantity`` e ``average_price``.
    """

    SUCCESS_STATUSES = {
        "SUCCESS",
        "OK",
        "ACCEPTED",
        "PARTIALLY_FILLED",
        "FILLED",
        "COMPLETED",
    }
    FAILURE_STATUSES = {"FAILED", "ERROR", "REJECTED", "CANCELLED", "EXPIRED"}
    PARTIAL_STATUSES = {"PARTIAL", "PARTIALLY_FILLED"}
    DISABLED_STATUSES = {"DISABLED"}

    def __init__(self) -> None:
        self._reports: list[Any] = []
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @classmethod
    def _first(cls, target: Any, names: tuple[str, ...], default: Any = None) -> Any:
        for name in names:
            value = cls._read(target, name, None)
            if value is not None:
                return value
        return default

    @staticmethod
    def _number(value: Any, default: float = 0.0) -> float:
        if value is None or isinstance(value, bool):
            return float(default)
        try:
            number = float(value)
        except (TypeError, ValueError):
            return float(default)
        return number if isfinite(number) else float(default)

    @classmethod
    def _status(cls, report: Any) -> str:
        value = cls._read(report, "status", "UNKNOWN")
        value = getattr(value, "value", value)
        return str(value or "UNKNOWN").strip().upper()

    @classmethod
    def _success(cls, report: Any, status: str) -> bool:
        explicit = cls._read(report, "success", None)
        if explicit is not None:
            return bool(explicit)
        return status in cls.SUCCESS_STATUSES

    @classmethod
    def _quantity(cls, report: Any) -> float:
        return max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    (
                        "executed_quantity",
                        "applied_quantity",
                        "filled_quantity",
                        "total_quantity",
                        "quantity",
                    ),
                    0.0,
                )
            ),
        )

    @classmethod
    def _price(cls, report: Any) -> float:
        return max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    ("average_price", "executed_price", "price"),
                    0.0,
                )
            ),
        )

    @staticmethod
    def _as_list(reports: Any) -> list[Any]:
        if reports is None:
            return []
        if isinstance(reports, Mapping):
            return [reports]
        if isinstance(reports, (str, bytes)):
            raise TypeError("reports deve ser um relatório ou coleção.")
        if isinstance(reports, Iterable):
            return list(reports)
        return [reports]

    def calculate(self, reports: Any) -> dict[str, Any]:
        items = self._as_list(reports)
        statuses = [self._status(report) for report in items]
        success_flags = [
            self._success(report, status)
            for report, status in zip(items, statuses)
        ]
        quantities = [self._quantity(report) for report in items]
        prices = [self._price(report) for report in items]

        total_quantity = sum(quantities)
        weighted_value = sum(
            quantity * price
            for quantity, price in zip(quantities, prices)
            if quantity > 0 and price > 0
        )
        priced_quantities = sum(
            quantity
            for quantity, price in zip(quantities, prices)
            if quantity > 0 and price > 0
        )
        nonzero_prices = [price for price in prices if price > 0]
        average_price = (
            weighted_value / priced_quantities
            if priced_quantities > 0
            else (mean(nonzero_prices) if nonzero_prices else 0.0)
        )

        execution_times = [
            self._number(
                self._first(report, ("execution_time", "latency", "latency_ms"), 0.0)
            )
            for report in items
        ]
        slippages = [
            self._number(self._first(report, ("slippage", "slippage_rate"), 0.0))
            for report in items
        ]
        fees = [
            self._number(self._first(report, ("fee", "fees_paid"), 0.0))
            for report in items
        ]
        attempts = [
            max(0, int(self._number(self._read(report, "attempts", 0))))
            for report in items
        ]

        successful = sum(success_flags)
        failed = len(items) - successful
        status_counts = Counter(statuses)
        partial = sum(status in self.PARTIAL_STATUSES for status in statuses)
        disabled = sum(status in self.DISABLED_STATUSES for status in statuses)
        success_rate = successful / len(items) if items else 0.0

        report = {
            "orders": len(items),
            "reports": len(items),
            "successful": successful,
            "failed": failed,
            "partial": partial,
            "disabled": disabled,
            "success_rate": round(success_rate, 8),
            "success_rate_percentage": round(success_rate * 100, 2),
            "quantity": round(total_quantity, 8),
            "total_quantity": round(total_quantity, 8),
            "average_price": round(average_price, 8),
            "executed_notional": round(weighted_value, 8),
            "total_execution_time": round(sum(execution_times), 8),
            "average_execution_time": round(
                mean(execution_times) if execution_times else 0.0,
                8,
            ),
            "average_slippage": round(
                mean(slippages) if slippages else 0.0,
                8,
            ),
            "total_fees": round(sum(fees), 8),
            "attempts": sum(attempts),
            "retries": sum(max(0, attempt - 1) for attempt in attempts),
            "statuses": dict(sorted(status_counts.items())),
        }
        self.last_report = dict(report)
        return report

    def update(self, report: Any) -> Any:
        if report is None:
            raise ValueError("report não pode ser None.")
        try:
            stored = deepcopy(report)
        except Exception:
            stored = report
        with self._lock:
            self._reports.append(stored)
        return report

    add = update

    def update_many(self, reports: Any) -> int:
        items = self._as_list(reports)
        for report in items:
            self.update(report)
        return len(items)

    def all(self) -> list[Any]:
        with self._lock:
            try:
                return deepcopy(self._reports)
            except Exception:
                return list(self._reports)

    def clear(self) -> None:
        with self._lock:
            self._reports.clear()
            self.last_report = {}

    reset = clear

    def summary(self) -> dict[str, Any]:
        return self.calculate(self.all())

    snapshot = summary


execution_statistics = ExecutionStatistics()
