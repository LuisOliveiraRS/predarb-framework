from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.liquidity_router.liquidity_level import LiquidityLevel
from app.orders.liquidity_router.liquidity_ranker import LiquidityRanker, liquidity_ranker
from app.orders.order_side import OrderSide


class LiquidityAllocator:
    """Divide quantidade entre níveis sem exceder ordem ou liquidez."""

    def __init__(self, *, ranker: LiquidityRanker | None = None) -> None:
        self.ranker = ranker if ranker is not None else liquidity_ranker
        self.last_report: dict[str, Any] = {}

    def allocate(
        self,
        quantity: Any,
        levels: Iterable[Any],
        side: OrderSide | str = OrderSide.BUY,
        *,
        max_venues: int | None = None,
    ) -> list[dict[str, Any]]:
        requested = float(quantity)
        if requested <= 0:
            raise ValueError("quantity deve ser maior que zero.")
        if max_venues is not None and int(max_venues) <= 0:
            raise ValueError("max_venues deve ser maior que zero.")

        resolved_side = OrderSide.parse(side)
        ranked = self.ranker.rank(levels, resolved_side)
        if max_venues is not None:
            ranked = ranked[: int(max_venues)]

        remaining = round(requested, 8)
        allocation: list[dict[str, Any]] = []
        for sequence, level in enumerate(ranked, start=1):
            if remaining <= 1e-8:
                break
            allocated = round(min(remaining, level.quantity), 8)
            if allocated <= 0:
                continue
            price = level.price_for(resolved_side)
            allocation.append(
                {
                    "exchange": level.exchange,
                    "connector": level.connector,
                    "quantity": allocated,
                    "price": price,
                    "available_quantity": level.quantity,
                    "spread": level.spread,
                    "notional": round(allocated * price, 8),
                    "sequence": sequence,
                    "level": level,
                }
            )
            remaining = round(max(0.0, remaining - allocated), 8)

        allocated_total = round(requested - remaining, 8)
        self.last_report = {
            "requested_quantity": round(requested, 8),
            "allocated_quantity": allocated_total,
            "unallocated_quantity": remaining,
            "complete": remaining <= 1e-8,
            "venues": len(allocation),
            "side": resolved_side.value,
        }
        return allocation


liquidity_allocator = LiquidityAllocator()
