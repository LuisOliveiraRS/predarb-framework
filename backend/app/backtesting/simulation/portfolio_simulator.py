class PortfolioSimulator:

    def __init__(self, capital):

        self.capital = capital

        self.equity_curve = [capital]

        self.trades = []

    def apply_trade(self, pnl):

        self.capital += pnl

        self.equity_curve.append(self.capital)

        self.trades.append(pnl)

    def equity(self):

        return self.capital


portfolio_simulator = PortfolioSimulator