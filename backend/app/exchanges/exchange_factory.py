from app.exchanges.exchange_registry import (
    exchange_registry,
)

from app.exchanges.paper_adapter import PaperAdapter


class ExchangeFactory:
    """
    Responsável por registrar
    todas as Exchanges.
    """

    def build(self):

        exchange_registry.register(

            "paper",

            PaperAdapter()

        )

        return exchange_registry


exchange_factory = ExchangeFactory()