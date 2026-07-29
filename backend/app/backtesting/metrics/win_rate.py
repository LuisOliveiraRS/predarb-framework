class WinRate:

    def calculate(self, trades):

        if not trades:

            return 0

        wins = len([t for t in trades if t > 0])

        return round(

            wins / len(trades) * 100,

            2

        )


win_rate = WinRate()