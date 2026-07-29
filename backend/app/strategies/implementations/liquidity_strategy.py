from app.strategies.base_strategy import BaseStrategy


class LiquidityStrategy(BaseStrategy):

    @property
    def name(self):

        return "Liquidity"

    def enabled(self):

        return True

    def analyze(self, opportunities):

        filtered = []

        for opportunity in opportunities:

            liquidity = opportunity.get(

                "liquidity",

                100

            )

            if liquidity >= 50:

                filtered.append(opportunity)

        return filtered


liquidity_strategy = LiquidityStrategy()