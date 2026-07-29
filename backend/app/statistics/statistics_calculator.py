from app.statistics.statistics_models import Statistics

from app.orders.order_repository import (
    order_repository
)

from app.positions.position_manager import (
    position_manager
)


class StatisticsCalculator:
    """
    Calcula todas as métricas
    do sistema.
    """

    def calculate(self):

        positions = position_manager.all()

        orders = order_repository.all()

        total_profit = position_manager.total_pnl()

        total_positions = len(positions)

        total_orders = len(orders)

        wins = len(
            [
                p
                for p in positions
                if p.pnl > 0
            ]
        )

        losses = len(
            [
                p
                for p in positions
                if p.pnl <= 0
            ]
        )

        if total_positions:

            win_rate = wins / total_positions * 100

            loss_rate = losses / total_positions * 100

        else:

            win_rate = 0

            loss_rate = 0

        roi = 0

        if total_positions:

            invested = sum(

                p.average_price * p.quantity

                for p in positions

            )

            if invested:

                roi = (
                    total_profit / invested
                ) * 100

        return Statistics(

            profit=round(total_profit, 2),

            roi=round(roi, 2),

            orders=total_orders,

            positions=total_positions,

            win_rate=round(win_rate, 2),

            loss_rate=round(loss_rate, 2),

            drawdown=0,

            profit_factor=0,

            latency=0,

            sharpe=0,

            sortino=0,

        )


statistics_calculator = StatisticsCalculator()