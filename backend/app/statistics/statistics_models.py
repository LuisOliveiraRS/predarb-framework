from dataclasses import dataclass


@dataclass
class Statistics:

    profit: float = 0.0

    roi: float = 0.0

    orders: int = 0

    positions: int = 0

    win_rate: float = 0.0

    loss_rate: float = 0.0

    drawdown: float = 0.0

    profit_factor: float = 0.0

    latency: float = 0.0

    sharpe: float = 0.0

    sortino: float = 0.0