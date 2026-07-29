from __future__ import annotations

import inspect
import logging
from collections.abc import Iterable, Mapping
from typing import Any


logger = logging.getLogger(__name__)


class MarketCollector:
    """Coleta mercados de conectores síncronos ou assíncronos."""

    @staticmethod
    def _as_list(value: Any, connector_name: str) -> list[Any]:
        if value is None:
            return []
        if isinstance(value, (str, bytes, Mapping)):
            raise TypeError(
                f"O conector {connector_name!r} deve retornar uma coleção."
            )
        if not isinstance(value, Iterable):
            raise TypeError(
                f"O conector {connector_name!r} deve retornar uma coleção."
            )
        return list(value)

    @staticmethod
    def _name(connector: Any) -> str:
        return str(
            getattr(connector, "name", None)
            or getattr(connector, "platform", None)
            or connector.__class__.__name__
        )

    @staticmethod
    def _method(connector: Any) -> Any:
        for method_name in ("fetch_markets", "get_markets"):
            method = getattr(connector, method_name, None)
            if callable(method):
                return method
        raise TypeError("O conector não implementa fetch_markets() ou get_markets().")

    def collect(self, connectors: Iterable[Any]) -> list[Any]:
        markets: list[Any] = []

        for connector in connectors:
            name = self._name(connector)
            try:
                method = self._method(connector)
                if inspect.iscoroutinefunction(method):
                    raise RuntimeError(
                        "Conector assíncrono recebido pelo fluxo síncrono; "
                        "utilize collect_async() ou MarketEngine.update_async()."
                    )
                result = method()
                if inspect.isawaitable(result):
                    close = getattr(result, "close", None)
                    if callable(close):
                        close()
                    raise RuntimeError(
                        "Conector assíncrono recebido pelo fluxo síncrono; "
                        "utilize collect_async() ou MarketEngine.update_async()."
                    )
                markets.extend(self._as_list(result, name))
            except Exception:
                logger.exception("Erro ao coletar mercados de %s.", name)

        return markets

    async def collect_async(self, connectors: Iterable[Any]) -> list[Any]:
        markets: list[Any] = []

        for connector in connectors:
            name = self._name(connector)
            try:
                result = self._method(connector)()
                if inspect.isawaitable(result):
                    result = await result
                markets.extend(self._as_list(result, name))
            except Exception:
                logger.exception("Erro ao coletar mercados de %s.", name)

        return markets


market_collector = MarketCollector()
