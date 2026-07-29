from app.strategies.base_strategy import BaseStrategy


class MomentumStrategy(BaseStrategy):

    @property
    def name(self):

        return "Momentum"

    def enabled(self):

        return False

    def analyze(self, opportunities):

        return []


momentum_strategy = MomentumStrategy()