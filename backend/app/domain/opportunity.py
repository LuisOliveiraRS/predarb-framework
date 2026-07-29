from dataclasses import dataclass, field
from datetime import datetime

from app.utils.time import utc_now


@dataclass
class Opportunity:

    question: str

    buy_yes_platform: str

    buy_no_platform: str

    yes_price: float

    no_price: float

    cost: float

    edge: float

    roi: float

    profit: float

    spread: float

    confidence: float

    risk_score: float = 0

    risk_level: str = "UNKNOWN"

    liquidity_score: float = 0

    slippage: float = 0

    execution_time: float = 0

    expected_profit: float = 0

    score: float = 0

    match_score: float = 1.0

    created_at: datetime = field(
        default_factory=utc_now
    )

    metadata: dict = field(
        default_factory=dict
    )