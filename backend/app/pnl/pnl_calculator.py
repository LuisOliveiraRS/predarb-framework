class PnLCalculator:
    """
    Calcula lucro e prejuízo
    de posições abertas e fechadas.
    """

    def calculate(self, position):

        return {

            "invested": position.invested,

            "expected_profit": position.expected_profit,

            "roi": position.roi

        }


pnl_calculator = PnLCalculator()