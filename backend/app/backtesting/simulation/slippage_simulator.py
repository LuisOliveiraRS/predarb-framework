class SlippageSimulator:

    def apply(self, price, slippage):

        return round(

            price * (1 + slippage),

            4

        )


slippage_simulator = SlippageSimulator()