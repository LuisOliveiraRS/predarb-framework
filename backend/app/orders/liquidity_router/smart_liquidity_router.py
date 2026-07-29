from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.liquidity_router.liquidity_allocator import (
    LiquidityAllocator,
    liquidity_allocator,
)
from app.orders.liquidity_router.liquidity_repository import (
    LiquidityRepository,
    liquidity_repository,
)
from app.orders.order import Order


class SmartLiquidityRouter:
    """Planeja alocação de liquidez; não chama exchanges."""

    def __init__(
        self,
        *,
        repository: LiquidityRepository | None = None,
        allocator: LiquidityAllocator | None = None,
    ) -> None:
        self.repository = repository if repository is not None else liquidity_repository
        self.allocator = allocator if allocator is not None else liquidity_allocator
        self.last_report: dict[str, Any] = {}

    def allocate(
        self,
        order: Order,
        levels: Iterable[Any] | None = None,
        *,
        require_full: bool = False,
        max_venues: int | None = None,
    ) -> list[dict[str, Any]]:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")
        source = list(levels) if levels is not None else self.repository.snapshot()
        allocation = self.allocator.allocate(
            order.remaining_quantity,
            source,
            order.side,
            max_venues=max_venues,
        )
        self.last_report = {
            **self.allocator.last_report,
            "order_id": order.id,
            "levels": len(source),
        }
        if require_full and not self.last_report["complete"]:
            raise ValueError(
                "Liquidez insuficiente: "
                f"faltam {self.last_report['unallocated_quantity']}."
            )
        return allocation

    def plan(self, order: Order, levels: Iterable[Any] | None = None, **options: Any) -> dict[str, Any]:
        allocation = self.allocate(order, levels, **options)
        return {
            **self.last_report,
            "allocation": [
                {key: value for key, value in item.items() if key != "level"}
                for item in allocation
            ],
        }


smart_liquidity_router = SmartLiquidityRouter()
