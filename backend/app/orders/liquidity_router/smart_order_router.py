from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.order import Order


class SmartOrderRouter:
    """Fachada legada sobre o SmartOrderRouter oficial do OMS."""

    def route(
        self,
        order: Order,
        venues: Iterable[Any] | None = None,
        *,
        levels: Iterable[Any] | None = None,
        require_full: bool = False,
        max_venues: int | None = None,
    ) -> dict[str, Any]:
        from app.orders.smart_order_router import smart_order_router

        plan = smart_order_router.build_plan(
            order,
            venues=venues,
            liquidity_levels=levels,
            require_full_liquidity=require_full,
            max_venues=max_venues,
        )
        return {
            "allocation": [dict(item) for item in plan.allocation],
            "route": plan.best_route,
            "plan": plan,
            "complete": plan.complete,
        }


smart_order_router = SmartOrderRouter()
