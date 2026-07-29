from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.orders.ai_router.execution_history import ExecutionHistory, execution_history


class RouterDataset:
    """Normaliza relatórios heterogêneos em linhas de aprendizado.

    Unidades oficiais:

    - ``latency_ms``: milissegundos;
    - ``slippage_rate`` e ``fee_rate``: taxa decimal;
    - ``executed_quantity``: quantidade executada.
    """

    SUCCESS_STATUSES = {
        "SUCCESS",
        "OK",
        "ACCEPTED",
        "PARTIALLY_FILLED",
        "FILLED",
        "COMPLETED",
    }

    def __init__(self, *, history: ExecutionHistory | None = None) -> None:
        self.history = history if history is not None else execution_history
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @classmethod
    def _nested(cls, target: Any, *path: str, default: Any = None) -> Any:
        current = target
        for field_name in path:
            current = cls._read(current, field_name, None)
            if current is None:
                return default
        return current

    @classmethod
    def _first(cls, target: Any, paths: tuple[tuple[str, ...], ...]) -> Any:
        for path in paths:
            value = cls._nested(target, *path, default=None)
            if value is not None:
                return value
        return None

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
        value = cls._first(
            report,
            (("status",), ("result", "status"), ("response", "status")),
        )
        value = getattr(value, "value", value)
        return str(value or "UNKNOWN").strip().upper()

    @classmethod
    def _success(cls, report: Any, status: str) -> bool:
        explicit = cls._first(report, (("success",), ("result", "success")))
        if explicit is not None:
            return bool(explicit)
        return status in cls.SUCCESS_STATUSES

    @classmethod
    def _timestamp(cls, report: Any) -> str:
        value = cls._first(
            report,
            (("timestamp",), ("created_at",), ("updated_at",)),
        )
        if isinstance(value, datetime):
            normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
            return normalized.isoformat()
        if value:
            return str(value)
        return datetime.now(timezone.utc).isoformat()

    @classmethod
    def _venue(cls, report: Any, fallback: str = "") -> str:
        value = cls._first(
            report,
            (
                ("venue",),
                ("exchange",),
                ("platform",),
                ("order", "platform"),
                ("result", "venue"),
                ("result", "exchange"),
                ("result", "platform"),
            ),
        )
        return str(value or fallback or "").strip()

    @classmethod
    def normalize(cls, venue: Any, report: Any) -> dict[str, Any]:
        venue_name = cls._venue(report, str(venue or ""))
        if not venue_name:
            raise ValueError("Não foi possível identificar a venue do relatório.")

        status = cls._status(report)
        quantity = max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    (
                        ("executed_quantity",),
                        ("applied_quantity",),
                        ("filled_quantity",),
                        ("quantity",),
                        ("result", "executed_quantity"),
                        ("result", "filled_quantity"),
                    ),
                )
            ),
        )
        price = max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    (
                        ("average_price",),
                        ("executed_price",),
                        ("price",),
                        ("result", "average_price"),
                        ("result", "price"),
                    ),
                )
            ),
        )
        notional = max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    (("executed_notional",), ("notional",), ("result", "notional")),
                ),
                quantity * price,
            ),
        )

        explicit_latency_ms = cls._first(
            report,
            (("latency_ms",), ("execution_time_ms",), ("result", "latency_ms")),
        )
        if explicit_latency_ms is not None:
            latency_ms = max(0.0, cls._number(explicit_latency_ms))
        else:
            execution_time_seconds = cls._first(
                report,
                (("execution_time",), ("result", "execution_time")),
            )
            if execution_time_seconds is not None:
                latency_ms = max(0.0, cls._number(execution_time_seconds) * 1000.0)
            else:
                latency_ms = max(
                    0.0,
                    cls._number(
                        cls._first(report, (("latency",), ("result", "latency")))
                    ),
                )

        slippage_rate = cls._number(
            cls._first(
                report,
                (
                    ("slippage_rate",),
                    ("slippage",),
                    ("result", "slippage_rate"),
                    ("result", "slippage"),
                ),
            )
        )
        fee_amount = max(
            0.0,
            cls._number(
                cls._first(
                    report,
                    (
                        ("fee",),
                        ("fees_paid",),
                        ("result", "fee"),
                        ("result", "fees_paid"),
                    ),
                )
            ),
        )
        explicit_fee_rate = cls._first(
            report,
            (("fee_rate",), ("result", "fee_rate")),
        )
        fee_rate = (
            max(0.0, cls._number(explicit_fee_rate))
            if explicit_fee_rate is not None
            else (fee_amount / notional if notional > 0 else 0.0)
        )

        return {
            "venue": venue_name,
            "status": status,
            "success": cls._success(report, status),
            "latency_ms": round(latency_ms, 8),
            "slippage_rate": round(slippage_rate, 10),
            "fee_rate": round(fee_rate, 10),
            "fee_amount": round(fee_amount, 8),
            "executed_quantity": round(quantity, 8),
            "average_price": round(price, 8),
            "executed_notional": round(notional, 8),
            "timestamp": cls._timestamp(report),
        }

    def build(
        self,
        history: Mapping[str, Iterable[Any]] | None = None,
    ) -> list[dict[str, Any]]:
        source = dict(history) if history is not None else self.history.all()
        dataset: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []

        for venue, reports in source.items():
            for index, report in enumerate(list(reports)):
                try:
                    dataset.append(self.normalize(venue, report))
                except (TypeError, ValueError) as exc:
                    rejected.append(
                        {"venue": str(venue), "index": index, "reason": str(exc)}
                    )

        self.last_report = {
            "rows": len(dataset),
            "venues": len({row["venue"].casefold() for row in dataset}),
            "rejected": rejected,
            "live_execution": False,
        }
        return dataset


router_dataset = RouterDataset()
