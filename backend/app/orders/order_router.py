from __future__ import annotations

import inspect
from collections.abc import Mapping
from typing import Any, Callable

from app.connectors.manager.connector_manager import connector_manager
from app.orders.order import Order


class OrderRouter:
    """Resolve o conector responsável por uma ordem e envia o objeto bruto.

    O Router não altera estado, não aplica fills e não persiste a ordem. Essas
    responsabilidades pertencem ao Dispatcher, à máquina de estados e ao
    OrderExecutor.
    """

    METHOD_CANDIDATES = (
        "place_order",
        "submit_order",
        "send_order",
        "create_order",
        "execute_order",
    )

    def __init__(self, *, manager: Any = None) -> None:
        self.manager = manager if manager is not None else connector_manager
        self.last_route: dict[str, Any] = {}

    @staticmethod
    def _platform(order: Any) -> str:
        platform = str(getattr(order, "platform", "") or "").strip()
        if not platform:
            raise ValueError("A ordem deve possuir uma plataforma válida.")
        return platform

    def _all_connectors(self) -> Mapping[str, Any]:
        all_method = getattr(self.manager, "all", None)
        if not callable(all_method):
            return {}
        connectors = all_method()
        return connectors if isinstance(connectors, Mapping) else {}

    def connector(self, platform: str) -> Any:
        normalized = str(platform or "").strip()
        if not normalized:
            raise ValueError("platform não pode ser vazio.")

        get_method = getattr(self.manager, "get", None)
        connector = get_method(normalized) if callable(get_method) else None
        if connector is not None:
            return connector

        wanted = normalized.casefold()
        for name, candidate in self._all_connectors().items():
            if str(name).strip().casefold() == wanted:
                return candidate

        raise LookupError(f"Connector {normalized!r} não encontrado.")

    @classmethod
    def _sender(cls, connector: Any) -> tuple[str, Callable[[Any], Any]]:
        for method_name in cls.METHOD_CANDIDATES:
            method = getattr(connector, method_name, None)
            if callable(method):
                return method_name, method
        raise AttributeError(
            "O conector não expõe um método de envio de ordens compatível: "
            + ", ".join(cls.METHOD_CANDIDATES)
            + "."
        )

    def route(self, order: Order, *, connector: Any = None) -> Any:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")

        platform = self._platform(order)
        resolved_connector = connector if connector is not None else self.connector(platform)
        method_name, sender = self._sender(resolved_connector)
        response = sender(order)

        if inspect.isawaitable(response):
            close = getattr(response, "close", None)
            if callable(close):
                close()
            raise TypeError(
                "O conector retornou uma coroutine. O OMS atual possui fluxo "
                "síncrono; use um adaptador síncrono para place_order()."
            )

        self.last_route = {
            "order_id": order.id,
            "platform": platform,
            "connector": resolved_connector.__class__.__name__,
            "method": method_name,
            "response_received": response is not None,
        }
        return response


order_router = OrderRouter()
