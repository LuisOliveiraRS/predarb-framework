class RealtimeMessage:
    """
    Fábrica de mensagens enviadas
    via WebSocket para o Dashboard.
    """

    @staticmethod
    def opportunity(opportunity):

        return {
            "type": "opportunity",
            "data": opportunity
        }

    @staticmethod
    def market(market):

        return {
            "type": "market",
            "data": market
        }

    @staticmethod
    def order(order):

        return {
            "type": "order",
            "data": order
        }

    @staticmethod
    def position(position):

        return {
            "type": "position",
            "data": position
        }

    @staticmethod
    def portfolio(portfolio):

        return {
            "type": "portfolio",
            "data": portfolio
        }

    @staticmethod
    def statistics(statistics):

        return {
            "type": "statistics",
            "data": statistics
        }

    @staticmethod
    def heartbeat():

        return {
            "type": "heartbeat"
        }