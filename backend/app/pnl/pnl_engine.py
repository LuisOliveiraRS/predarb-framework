from app.pnl.pnl_calculator import pnl_calculator


class PnLEngine:

    """
    Responsável por atualizar
    o PnL das posições.
    """

    def process(self, positions):

        reports = []

        for position in positions:

            reports.append(

                pnl_calculator.calculate(position)

            )

        return reports


pnl_engine = PnLEngine()