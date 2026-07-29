from __future__ import annotations

from collections import Counter
from collections.abc import Iterable, Mapping
from copy import deepcopy
from math import isfinite
from statistics import mean
from threading import RLock
from typing import Any


class ExecutionStatistics:
    """
    Agregador thread-safe dos relatórios da
    camada Execution.

    Aceita relatórios de planejamento e resultados
    de execução live.

    Preserva as chaves legadas:

        orders
        average_latency
        average_slippage
        success_rate
    """

    SUCCESS_STATUSES = {
        "SUCCESS",
        "FILLED",
        "COMPLETED",
    }

    FAILURE_STATUSES = {
        "FAILED",
        "ERROR",
        "CANCELLED",
    }

    READY_STATUSES = {
        "READY",
        "APPROVED",
    }

    REJECTED_STATUSES = {
        "REJECTED",
    }

    DISABLED_STATUSES = {
        "DISABLED",
    }

    def __init__(self) -> None:
        self._reports: list[Any] = []

        self._lock = RLock()

    @staticmethod
    def _read(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(
            target,
            Mapping,
        ):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @classmethod
    def _nested(
        cls,
        target: Any,
        *path: str,
        default: Any = None,
    ) -> Any:
        current = target

        for field_name in path:
            current = cls._read(
                current,
                field_name,
                None,
            )

            if current is None:
                return default

        return current

    @staticmethod
    def _number(
        value: Any,
    ) -> float | None:
        if (
            value is None
            or isinstance(
                value,
                bool,
            )
        ):
            return None

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return None

        if not isfinite(
            number
        ):
            return None

        return number

    @classmethod
    def _first_number(
        cls,
        report: Any,
        candidates: tuple[
            tuple[str, ...],
            ...,
        ],
    ) -> float | None:
        for path in candidates:
            value = cls._nested(
                report,
                *path,
                default=None,
            )

            number = cls._number(
                value
            )

            if number is not None:
                return number

        return None

    @classmethod
    def _status(
        cls,
        report: Any,
    ) -> str:
        status = cls._read(
            report,
            "status",
            "UNKNOWN",
        )

        return (
            str(
                status
                or "UNKNOWN"
            )
            .strip()
            .upper()
        )

    @classmethod
    def _is_executed(
        cls,
        report: Any,
        status: str,
    ) -> bool:
        if (
            status in cls.SUCCESS_STATUSES
            or status in cls.FAILURE_STATUSES
        ):
            return True

        executed = cls._read(
            report,
            "executed",
            None,
        )

        if executed is not None:
            return bool(
                executed
            )

        return False

    @classmethod
    def _is_success(
        cls,
        report: Any,
        status: str,
    ) -> bool:
        success = cls._read(
            report,
            "success",
            None,
        )

        if success is not None:
            return bool(
                success
            )

        return (
            status
            in cls.SUCCESS_STATUSES
        )

    @staticmethod
    def _safe_copy(
        report: Any,
    ) -> Any:
        try:
            return deepcopy(
                report
            )

        except Exception:
            return report

    @property
    def reports(self) -> list[Any]:
        """
        Propriedade legada.

        Retorna uma cópia segura dos relatórios.
        """

        return self.all()

    def update(
        self,
        report: Any,
    ) -> Any:
        if report is None:
            raise ValueError(
                "report não pode ser None."
            )

        stored = self._safe_copy(
            report
        )

        with self._lock:
            self._reports.append(
                stored
            )

        return report

    add = update

    def update_many(
        self,
        reports: Iterable[Any],
    ) -> int:
        if isinstance(
            reports,
            (
                str,
                bytes,
                Mapping,
            ),
        ):
            raise TypeError(
                "reports deve ser uma coleção "
                "de relatórios."
            )

        count = 0

        for report in reports:
            self.update(
                report
            )

            count += 1

        return count

    def all(self) -> list[Any]:
        with self._lock:
            return [
                self._safe_copy(
                    report
                )
                for report
                in self._reports
            ]

    def clear(self) -> None:
        with self._lock:
            self._reports.clear()

    reset = clear

    def summary(
        self,
    ) -> dict[str, Any]:
        reports = self.all()

        if not reports:
            return {
                "reports": 0,
                "orders": 0,
                "ready": 0,
                "rejected": 0,
                "disabled": 0,
                "executed": 0,
                "successful": 0,
                "failed": 0,
                "average_latency": 0.0,
                "average_latency_ms": 0.0,
                "average_slippage": 0.0,
                "success_rate": 0.0,
                "success_rate_percentage": 0.0,
                "total_expected_profit": 0.0,
                "total_realized_profit": 0.0,
                "statuses": {},
            }

        statuses = [
            self._status(
                report
            )
            for report in reports
        ]

        status_counts = Counter(
            statuses
        )

        executed_flags = [
            self._is_executed(
                report,
                status,
            )
            for report, status
            in zip(
                reports,
                statuses,
            )
        ]

        success_flags = [
            self._is_success(
                report,
                status,
            )
            for report, status
            in zip(
                reports,
                statuses,
            )
        ]

        executed = sum(
            executed_flags
        )

        successful = sum(
            1
            for (
                was_executed,
                was_successful,
            )
            in zip(
                executed_flags,
                success_flags,
            )
            if (
                was_executed
                and was_successful
            )
        )

        failed = sum(
            1
            for (
                was_executed,
                was_successful,
            )
            in zip(
                executed_flags,
                success_flags,
            )
            if (
                was_executed
                and not was_successful
            )
        )

        latencies = [
            value
            for report in reports
            if (
                value := self._first_number(
                    report,
                    (
                        (
                            "latency_ms",
                        ),
                        (
                            "execution_time_ms",
                        ),
                        (
                            "execution_time",
                        ),
                        (
                            "latency",
                        ),
                        (
                            "result",
                            "latency_ms",
                        ),
                        (
                            "result",
                            "execution_time_ms",
                        ),
                    ),
                )
            )
            is not None
        ]

        slippages = [
            value
            for report in reports
            if (
                value := self._first_number(
                    report,
                    (
                        (
                            "slippage_rate",
                        ),
                        (
                            "slippage",
                        ),
                        (
                            "result",
                            "slippage_rate",
                        ),
                        (
                            "result",
                            "slippage",
                        ),
                    ),
                )
            )
            is not None
        ]

        expected_profits = [
            value
            for report in reports
            if (
                value := self._first_number(
                    report,
                    (
                        (
                            "expected_profit",
                        ),
                        (
                            "plan",
                            "expected_profit",
                        ),
                    ),
                )
            )
            is not None
        ]

        realized_profits = [
            value
            for report in reports
            if (
                value := self._first_number(
                    report,
                    (
                        (
                            "realized_profit",
                        ),
                        (
                            "result",
                            "realized_profit",
                        ),
                        (
                            "result",
                            "profit",
                        ),
                    ),
                )
            )
            is not None
        ]

        success_rate = (
            successful
            / executed
            if executed > 0
            else 0.0
        )

        ready = sum(
            status_counts.get(
                status,
                0,
            )
            for status
            in self.READY_STATUSES
        )

        rejected = sum(
            status_counts.get(
                status,
                0,
            )
            for status
            in self.REJECTED_STATUSES
        )

        disabled = sum(
            status_counts.get(
                status,
                0,
            )
            for status
            in self.DISABLED_STATUSES
        )

        average_latency = (
            mean(
                latencies
            )
            if latencies
            else 0.0
        )

        average_slippage = (
            mean(
                slippages
            )
            if slippages
            else 0.0
        )

        return {
            "reports": len(
                reports
            ),
            "orders": len(
                reports
            ),
            "ready": ready,
            "rejected": rejected,
            "disabled": disabled,
            "executed": executed,
            "successful": successful,
            "failed": failed,
            "average_latency": round(
                average_latency,
                6,
            ),
            "average_latency_ms": round(
                average_latency,
                6,
            ),
            "average_slippage": round(
                average_slippage,
                8,
            ),
            "success_rate": round(
                success_rate,
                6,
            ),
            "success_rate_percentage": round(
                success_rate * 100,
                2,
            ),
            "total_expected_profit": round(
                sum(
                    expected_profits
                ),
                6,
            ),
            "total_realized_profit": round(
                sum(
                    realized_profits
                ),
                6,
            ),
            "statuses": dict(
                sorted(
                    status_counts.items()
                )
            ),
        }

    snapshot = summary


execution_statistics = ExecutionStatistics()