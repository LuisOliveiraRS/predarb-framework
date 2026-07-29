from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.orders.ai_router.adaptive_selector import AdaptiveSelector, adaptive_selector
from app.orders.liquidity_router.liquidity_level import LiquidityLevel
from app.orders.liquidity_router.smart_liquidity_router import (
    SmartLiquidityRouter,
    smart_liquidity_router,
)
from app.orders.order import Order
from app.orders.order_side import OrderSide
from app.orders.router.best_route_selector import BestRouteSelector, best_route_selector
from app.orders.router.execution_route import ExecutionRoute
from app.orders.router.router_metrics import RouterMetrics, router_metrics
from app.orders.slippage_engine import SlippageEngine, slippage_engine
from app.orders.venue_selection.smart_venue_selector import (
    SmartVenueSelector,
    smart_venue_selector,
)
from app.orders.venue_selection.venue import Venue


@dataclass(slots=True)
class SmartRoutePlan:
    order: Order
    venues: list[Venue]
    routes: list[ExecutionRoute]
    allocation: list[dict[str, Any]]
    best_route: ExecutionRoute | None
    complete: bool
    allocated_quantity: float
    unallocated_quantity: float
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def selected_venue(self) -> Venue | None:
        if self.best_route is None:
            return None
        selected = self.best_route.exchange.casefold()
        return next(
            (venue for venue in self.venues if venue.name.casefold() == selected),
            None,
        )

    @property
    def valid(self) -> bool:
        return (
            self.best_route is not None
            and bool(self.routes)
            and self.allocated_quantity > 0
        )

    @property
    def routing_mode(self) -> str:
        return str(self.metadata.get("routing_mode", "SMART")).upper()

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order.id,
            "valid": self.valid,
            "routing_mode": self.routing_mode,
            "complete": self.complete,
            "allocated_quantity": self.allocated_quantity,
            "unallocated_quantity": self.unallocated_quantity,
            "selected_venue": self.selected_venue.name if self.selected_venue else None,
            "best_route": self.best_route.to_dict() if self.best_route else None,
            "venues": [venue.to_dict() for venue in self.venues],
            "routes": [route.to_dict() for route in self.routes],
            "allocation": [dict(item) for item in self.allocation],
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }


class SmartOrderRouter:
    """Seleciona e pontua rotas sem enviar ordens.

    ``SMART`` usa o score determinístico de venue. ``ADAPTIVE`` combina esse
    score com histórico real, mantendo o score determinístico durante cold
    start. Nenhuma das modalidades chama conectores.
    """

    def __init__(
        self,
        *,
        venue_selector: SmartVenueSelector | None = None,
        liquidity_router: SmartLiquidityRouter | None = None,
        route_selector: BestRouteSelector | None = None,
        slippage: SlippageEngine | None = None,
        metrics: RouterMetrics | None = None,
        adaptive_selector_service: AdaptiveSelector | None = None,
    ) -> None:
        self.venue_selector = venue_selector if venue_selector is not None else smart_venue_selector
        self.liquidity_router = liquidity_router if liquidity_router is not None else smart_liquidity_router
        self.route_selector = route_selector if route_selector is not None else best_route_selector
        self.slippage = slippage if slippage is not None else slippage_engine
        self.metrics = metrics if metrics is not None else router_metrics
        self.adaptive_selector = (
            adaptive_selector_service
            if adaptive_selector_service is not None
            else adaptive_selector
        )
        self.last_plan: SmartRoutePlan | None = None

    @staticmethod
    def _levels_from_venues(
        order: Order,
        venues: list[Venue],
    ) -> tuple[list[LiquidityLevel], list[str]]:
        levels: list[LiquidityLevel] = []
        warnings: list[str] = []
        for venue in venues:
            bid = venue.bid
            ask = venue.ask
            if bid <= 0 or ask <= 0:
                if order.price <= 0:
                    warnings.append(f"PRICE_MISSING:{venue.name}")
                    continue
                bid = bid if bid > 0 else order.price
                ask = ask if ask > 0 else order.price
                warnings.append(f"PRICE_FROM_PARENT_ORDER:{venue.name}")
            levels.append(
                LiquidityLevel(
                    exchange=venue.name,
                    connector=venue.connector,
                    bid=bid,
                    ask=ask,
                    quantity=venue.liquidity,
                    spread=max(0.0, ask - bid),
                    enabled=venue.enabled,
                    metadata={"source": "venue"},
                )
            )
        return levels, warnings

    def build_plan(
        self,
        order: Order,
        venues: Iterable[Any] | None = None,
        *,
        liquidity_levels: Iterable[Any] | None = None,
        require_full_liquidity: bool = False,
        max_venues: int | None = None,
        min_reliability: float = 0.0,
        max_latency: float | None = None,
        max_fee: float | None = None,
        adaptive: bool = False,
    ) -> SmartRoutePlan:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        eligible = self.venue_selector.select(
            order,
            venues,
            min_reliability=min_reliability,
            max_latency=max_latency,
            max_fee=max_fee,
            require_liquidity=True,
        )
        warnings: list[str] = []
        adaptive_report: dict[str, Any] = {}
        adaptive_scores: dict[str, float] = {}

        if adaptive and eligible:
            adaptive_ranking = self.adaptive_selector.rank(eligible, order)
            eligible = [venue for _, venue in adaptive_ranking]
            adaptive_scores = {
                venue.name.casefold(): float(score)
                for score, venue in adaptive_ranking
            }
            adaptive_report = dict(self.adaptive_selector.last_report)
            ranking_details = adaptive_report.get("ranking", [])
            if ranking_details and all(item.get("cold_start", False) for item in ranking_details):
                warnings.append("ADAPTIVE_COLD_START")

        if liquidity_levels is None:
            levels, derived_warnings = self._levels_from_venues(order, eligible)
            warnings.extend(derived_warnings)
        else:
            eligible_names = {venue.name.casefold() for venue in eligible}
            levels = [LiquidityLevel.from_value(level) for level in liquidity_levels]
            levels = [
                level
                for level in levels
                if level.exchange.casefold() in eligible_names
            ]

        allocation = (
            self.liquidity_router.allocate(
                order,
                levels,
                require_full=False,
                max_venues=max_venues,
            )
            if levels
            else []
        )
        allocation_report = (
            dict(self.liquidity_router.last_report)
            if levels
            else {
                "requested_quantity": order.remaining_quantity,
                "allocated_quantity": 0.0,
                "unallocated_quantity": order.remaining_quantity,
                "complete": False,
                "venues": 0,
            }
        )

        venues_by_name = {venue.name.casefold(): venue for venue in eligible}
        routes: list[ExecutionRoute] = []
        public_allocation: list[dict[str, Any]] = []
        routing_mode = "ADAPTIVE" if adaptive else "SMART"

        for item in allocation:
            level = item["level"]
            venue = venues_by_name[level.exchange.casefold()]
            quantity = float(item["quantity"])
            price = float(item["price"])
            expected_notional = round(quantity * price, 8)
            expected_fee = round(expected_notional * venue.fee, 8)
            slippage_rate = (
                self.slippage.rate(order.price, price, order.side)
                if order.price > 0
                else 0.0
            )
            slippage_amount = (
                self.slippage.amount(order.price, price, quantity, order.side)
                if order.price > 0
                else 0.0
            )
            total_cost = (
                expected_notional + expected_fee
                if OrderSide.parse(order.side) is OrderSide.BUY
                else max(0.0, expected_notional - expected_fee)
            )
            route_score = adaptive_scores.get(venue.name.casefold(), venue.score)
            route = ExecutionRoute(
                exchange=venue.name,
                connector=venue.connector,
                latency=venue.latency,
                liquidity=venue.liquidity,
                fee=venue.fee,
                score=route_score,
                allocation_quantity=quantity,
                expected_price=price,
                slippage_rate=slippage_rate,
                slippage_amount=slippage_amount,
                expected_notional=expected_notional,
                expected_fee=expected_fee,
                total_cost=round(total_cost, 8),
                metadata={
                    "spread": level.spread,
                    "sequence": item["sequence"],
                    "venue_score": venue.score,
                    "adaptive_score": route_score if adaptive else None,
                    "routing_mode": routing_mode,
                },
            )
            routes.append(route)
            public_allocation.append(
                {
                    "exchange": venue.name,
                    "connector": route.connector_name,
                    "quantity": quantity,
                    "price": price,
                    "notional": expected_notional,
                    "sequence": item["sequence"],
                    "route_score": route_score,
                }
            )

        best = self.route_selector.select(order, routes)
        if best is not None:
            self.metrics.register(best)
        complete = bool(allocation_report.get("complete", False))
        if not complete:
            warnings.append("LIQUIDITY_ALLOCATION_INCOMPLETE")
        if require_full_liquidity and not complete:
            warnings.append("FULL_LIQUIDITY_REQUIRED")

        plan = SmartRoutePlan(
            order=order,
            venues=eligible,
            routes=routes,
            allocation=public_allocation,
            best_route=best,
            complete=complete,
            allocated_quantity=float(allocation_report.get("allocated_quantity", 0.0)),
            unallocated_quantity=float(
                allocation_report.get("unallocated_quantity", order.remaining_quantity)
            ),
            warnings=list(dict.fromkeys(warnings)),
            metadata={
                "live_execution": False,
                "routing_mode": routing_mode,
                "adaptive": bool(adaptive),
                "require_full_liquidity": bool(require_full_liquidity),
                "venue_selection": dict(self.venue_selector.last_report),
                "adaptive_ranking": adaptive_report,
                "liquidity_allocation": allocation_report,
            },
        )
        self.last_plan = plan
        return plan

    plan = build_plan

    def select(
        self,
        order: Order,
        venues: Iterable[Any] | None = None,
        **options: Any,
    ) -> Venue | None:
        return self.build_plan(order, venues, **options).selected_venue

    route = select


smart_order_router = SmartOrderRouter()
