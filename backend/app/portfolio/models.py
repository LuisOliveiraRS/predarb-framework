from dataclasses import dataclass
from datetime import datetime


@dataclass
class Position:

    id: int

    market: str

    platform_yes: str

    platform_no: str

    stake: float

    expected_profit: float

    roi: float

    opened_at: datetime

    status: str = "OPEN"