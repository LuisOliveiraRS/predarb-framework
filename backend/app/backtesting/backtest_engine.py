from app.backtesting.replay.replay_engine import ReplayEngine
from app.backtesting.simulation.portfolio_simulator import PortfolioSimulator
from app.backtesting.backtest_statistics import backtest_statistics


class BacktestEngine:

    def run(self, dataframe, strategy, config):

        replay = ReplayEngine(dataframe)

        portfolio = PortfolioSimulator(
            config.initial_capital
        )

        while replay.has_next():

            market = replay.next()

            signals = strategy.analyze([market])

            for signal in signals:

                pnl = signal.get("profit", 0)

                portfolio.apply_trade(pnl)

        return backtest_statistics.generate(
            portfolio
        )


backtest_engine = BacktestEngine()