from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from app.orders.router.execution_route import ExecutionRoute
from app.orders.router.route_repository import RouteRepository, route_repository


class BestRouteSelector:
    def __init__(self, *, repository: RouteRepository | None = None) -> None:
        self.repository = repository if repository is not None else route_repository
        self.last_report: dict[str, Any] = {}

    def rank(
        self,
        order: Any = None,
        routes: Iterable[Any] | None = None,
    ) -> list[ExecutionRoute]:
        del order
        candidates = list(routes) if routes is not None else self.repository.all()
        resolved = [ExecutionRoute.from_value(route) for route in candidates]
        eligible = [route for route in resolved if route.enabled]
        ranked = sorted(
            eligible,
            key=lambda route: (
                -route.score,
                route.total_cost,
                route.latency,
                route.fee,
                route.exchange.lower(),
            ),
        )
        return ranked

    def select(
        self,
        order: Any = None,
        routes: Iterable[Any] | None = None,
    ) -> ExecutionRoute | None:
        ranked = self.rank(order, routes)
        selected = ranked[0] if ranked else None
        self.last_report = {
            "routes": len(ranked),
            "selected": selected.exchange if selected else None,
            "ranking": [route.to_dict() for route in ranked],
        }
        return selected


best_route_selector = BestRouteSelector()
