from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.trading.execution_result import ExecutionResult
from app.trading.trade import Trade
from app.trading.trade_report import TradeReport
from app.trading.trade_repository import TradeRepository, trade_repository


class TradeManager:
    """Serviço oficial de criação, registro e consulta de trades."""

    def __init__(self, repository: TradeRepository | None = None) -> None:
        self.repository = repository or trade_repository
        self.last_report: dict[str, Any] = {}

    def create(
        self,
        order: Any,
        report: Any,
        *,
        trade_id: str | None = None,
        metadata: Mapping[str, Any] | None = None,
    ) -> Trade:
        trade = Trade(
            order,
            report,
            trade_id=trade_id,
            metadata=metadata,
        )
        stored = self.repository.add(trade)
        self.last_report = {
            "status": "CREATED",
            "trade_id": stored.id,
            "order_id": stored.order_id,
            "success": stored.success,
            "repository_count": self.repository.count(),
        }
        return stored

    def create_from_result(
        self,
        result: ExecutionResult,
        *,
        order: Any = None,
        include_failed: bool = True,
        metadata: Mapping[str, Any] | None = None,
    ) -> Trade | None:
        if not isinstance(result, ExecutionResult):
            raise TypeError("result deve ser uma instância de ExecutionResult.")
        if not result.success and not include_failed:
            self.last_report = {
                "status": "SKIPPED",
                "reason": "FAILED_RESULT",
                "repository_count": self.repository.count(),
            }
            return None

        resolved_order = order or getattr(result.context, "order", None)
        if resolved_order is None:
            raise ValueError("Não foi possível resolver a ordem do resultado.")

        report = result.report
        if report is None:
            report = {
                "status": result.status,
                "success": result.success,
                "error": result.error,
                "metadata": dict(result.metadata),
            }

        merged_metadata = dict(metadata or {})
        merged_metadata.setdefault("execution_result", result.to_dict())
        return self.create(
            resolved_order,
            report,
            metadata=merged_metadata,
        )

    def report(self, trade_or_id: Trade | str) -> TradeReport:
        trade = (
            trade_or_id
            if isinstance(trade_or_id, Trade)
            else self.repository.require(str(trade_or_id))
        )
        return TradeReport(trade)

    def get(self, trade_id: str) -> Trade | None:
        return self.repository.get(trade_id)

    def all(self) -> list[Trade]:
        return self.repository.all()

    list = all

    def by_order(self, order_or_id: Any) -> list[Trade]:
        order_id = (
            str(getattr(order_or_id, "id"))
            if not isinstance(order_or_id, str)
            else order_or_id
        )
        return self.repository.by_order(order_id)

    def clear(self) -> None:
        self.repository.clear()
        self.last_report = {}

    def status(self) -> dict[str, Any]:
        return {
            "repository": self.repository.status(),
            "last_report": dict(self.last_report),
        }


trade_manager = TradeManager()
