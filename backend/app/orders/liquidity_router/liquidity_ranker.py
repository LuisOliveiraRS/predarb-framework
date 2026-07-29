from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.liquidity_router.liquidity_level import LiquidityLevel
from app.orders.order_side import OrderSide


class LiquidityRanker:
    def rank(
        self,
        levels: Iterable[Any],
        side: OrderSide | str = OrderSide.BUY,
    ) -> list[LiquidityLevel]:
        resolved_side = OrderSide.parse(side)
        eligible = [LiquidityLevel.from_value(level) for level in levels]
        eligible = [level for level in eligible if level.available]

        if resolved_side is OrderSide.BUY:
            key = lambda level: (
                level.ask,
                level.spread,
                -level.quantity,
                level.exchange.lower(),
            )
        else:
            key = lambda level: (
                -level.bid,
                level.spread,
                -level.quantity,
                level.exchange.lower(),
            )
        return sorted(eligible, key=key)


liquidity_ranker = LiquidityRanker()
