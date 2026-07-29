from app.backtesting.metrics.sharpe_ratio import sharpe_ratio
from app.backtesting.metrics.sortino_ratio import sortino_ratio
from app.backtesting.metrics.max_drawdown import max_drawdown
from app.backtesting.metrics.win_rate import win_rate
from app.backtesting.metrics.profit_factor import profit_factor


class BacktestStatistics:

    def generate(self, portfolio):

        returns = portfolio.trades

        return {

            "final_equity": round(

                portfolio.equity(),

                2

            ),

            "sharpe": sharpe_ratio.calculate(returns),

            "sortino": sortino_ratio.calculate(returns),

            "max_drawdown": max_drawdown.calculate(

                portfolio.equity_curve

            ),

            "win_rate": win_rate.calculate(returns),

            "profit_factor": profit_factor.calculate(returns),

            "trades": len(returns)

        }


backtest_statistics = BacktestStatistics()