from __future__ import annotations

from collections.abc import Iterable
from threading import RLock
from typing import Any

from app.orders.router.execution_route import ExecutionRoute


class RouteRepository:
    """Repositório sem rotas fictícias pré-carregadas."""

    def __init__(self, routes: Iterable[Any] | None = None) -> None:
        self._routes: dict[str, ExecutionRoute] = {}
        self._lock = RLock()
        if routes is not None:
            self.add_many(routes)

    @property
    def routes(self) -> list[ExecutionRoute]:
        return self.all()

    def add(self, route: Any, *, replace: bool = True) -> ExecutionRoute:
        resolved = ExecutionRoute.from_value(route)
        key = resolved.exchange.casefold()
        with self._lock:
            if key in self._routes and not replace:
                raise ValueError(f"Rota já registrada: {resolved.exchange}.")
            self._routes[key] = resolved
        return resolved

    def add_many(self, routes: Iterable[Any], *, replace: bool = True) -> list[ExecutionRoute]:
        return [self.add(route, replace=replace) for route in routes]

    def get(self, exchange: Any, default: Any = None) -> ExecutionRoute | Any:
        with self._lock:
            return self._routes.get(str(exchange or "").strip().casefold(), default)

    def remove(self, exchange: Any) -> ExecutionRoute | None:
        with self._lock:
            return self._routes.pop(str(exchange or "").strip().casefold(), None)

    def all(self) -> list[ExecutionRoute]:
        with self._lock:
            return list(self._routes.values())

    list = all

    def enabled(self) -> list[ExecutionRoute]:
        return [route for route in self.all() if route.enabled]

    def clear(self) -> None:
        with self._lock:
            self._routes.clear()


route_repository = RouteRepository()
