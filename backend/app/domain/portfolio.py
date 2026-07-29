from dataclasses import dataclass


@dataclass
class Portfolio:

    bankroll: float

    invested: float

    available: float

    unrealized_pnl: float

    realized_pnl: float