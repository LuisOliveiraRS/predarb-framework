import numpy as np


class SharpeRatio:

    def calculate(self, returns):

        if len(returns) == 0:

            return 0

        mean = np.mean(returns)

        std = np.std(returns)

        if std == 0:

            return 0

        return round(

            (mean / std) * np.sqrt(252),

            4

        )


sharpe_ratio = SharpeRatio()