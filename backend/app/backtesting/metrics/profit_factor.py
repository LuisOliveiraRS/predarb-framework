class ProfitFactor:

    def calculate(self, trades):

        gains = sum(t for t in trades if t > 0)

        losses = abs(sum(t for t in trades if t < 0))

        if losses == 0:

            return 0

        return round(gains / losses, 4)


profit_factor = ProfitFactor()