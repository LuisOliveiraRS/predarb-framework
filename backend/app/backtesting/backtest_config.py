from dataclasses import dataclass
from datetime import datetime


@dataclass
class BacktestConfig:

    start: datetime

    end: datetime

    initial_capital: float = 10000

    commission: float = 0.001

    slippage: float = 0.002

    latency_ms: int = 120

    strategy: str = "Arbitrage"