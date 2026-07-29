from app.strategies.base_strategy import BaseStrategy


class ArbitrageStrategy(BaseStrategy):

    @property
    def name(self):

        return "Arbitrage"

    def enabled(self):

        return True

    def analyze(self, opportunities):

        return opportunities


arbitrage_strategy = ArbitrageStrategy()