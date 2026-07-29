from app.strategies.base_strategy import BaseStrategy


class MeanReversionStrategy(BaseStrategy):

    @property
    def name(self):

        return "MeanReversion"

    def enabled(self):

        return False

    def analyze(self, opportunities):

        return []


mean_reversion_strategy = MeanReversionStrategy()