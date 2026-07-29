class MaxDrawdown:

    def calculate(self, equity_curve):

        peak = equity_curve[0]

        max_dd = 0

        for value in equity_curve:

            peak = max(peak, value)

            dd = (peak - value) / peak

            max_dd = max(max_dd, dd)

        return round(max_dd * 100, 2)


max_drawdown = MaxDrawdown()