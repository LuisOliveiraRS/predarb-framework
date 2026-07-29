from dataclasses import dataclass
from datetime import datetime


@dataclass
class Trade:

    question: str

    pnl: float

    roi: float

    opened_at: datetime

    closed_at: datetime | None = None