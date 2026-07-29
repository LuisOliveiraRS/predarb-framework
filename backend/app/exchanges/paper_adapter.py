from app.exchanges.base_adapter import BaseExchangeAdapter

from app.paper.paper_order_executor import paper_order_executor


class PaperAdapter(BaseExchangeAdapter):
    """
    Adapter responsável pelo modo Paper Trading.
    """

    def __init__(self):

        self.connected = False

    def connect(self):

        self.connected = True

        return True

    def disconnect(self):

        self.connected = False

    def place_order(self, order):

        return paper_order_executor.execute(order)

    def cancel_order(self, order):

        return True

    def get_order(self, order_id):

        return None

    def get_balance(self):

        return {}

    def get_positions(self):

        return []

    def ping(self):

        return 0.001

    def health(self):

        return {

            "connected": self.connected,

            "latency": self.ping()

        }