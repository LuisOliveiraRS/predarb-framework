from typing import Dict

from app.exchanges.base_adapter import BaseExchangeAdapter


class ExchangeRegistry:

    """
    Registry das Exchanges.
    """

    def __init__(self):

        self._adapters: Dict[str, BaseExchangeAdapter] = {}

    def register(self, name, adapter):

        self._adapters[name.lower()] = adapter

    def exists(self, name):

        return name.lower() in self._adapters

    def remove(self, name):

        self._adapters.pop(name.lower(), None)

    def get(self, name):

        adapter = self._adapters.get(name.lower())

        if adapter is None:

            raise ValueError(

                f"Exchange '{name}' não registrada."

            )

        return adapter

    def all(self):

        return self._adapters

    def names(self):

        return list(self._adapters.keys())


exchange_registry = ExchangeRegistry()