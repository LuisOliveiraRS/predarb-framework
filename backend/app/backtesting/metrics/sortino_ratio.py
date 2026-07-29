import numpy as np


class SortinoRatio:

    def calculate(self, returns):

        negative = [r for r in returns if r < 0]

        if len(negative) == 0:

            return 0

        downside = np.std(negative)

        if downside == 0:

            return 0

        return round(

            np.mean(returns) /

            downside,

            4

        )


sortino_ratio = SortinoRatio()