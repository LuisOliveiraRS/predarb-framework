class MarketCache:

    """
    Cache em memória.
    """

    def __init__(self):

        self.markets = []

    def update(self, markets):

        self.markets = markets

    def all(self):

        return self.markets


market_cache = MarketCache()