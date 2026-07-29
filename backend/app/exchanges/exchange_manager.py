from app.exchanges.exchange_factory import exchange_factory


class ExchangeManager:

    """
    Camada única de comunicação
    com qualquer Exchange.
    """

    def __init__(self):

        self.registry = exchange_factory.build()

    def adapter(self, exchange):

        return self.registry.get(exchange)

    def execute(self, order):

        adapter = self.adapter(order.platform)

        return adapter.place_order(order)

    def cancel(self, exchange, order):

        adapter = self.adapter(exchange)

        return adapter.cancel_order(order)

    def get_balance(self, exchange):

        adapter = self.adapter(exchange)

        return adapter.get_balance()

    def get_positions(self, exchange):

        adapter = self.adapter(exchange)

        return adapter.get_positions()

    def health(self, exchange):

        adapter = self.adapter(exchange)

        return adapter.health()


exchange_manager = ExchangeManager()