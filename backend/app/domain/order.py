from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.utils.time import utc_now


@dataclass
class Order:
    platform: str
    question: str
    side: str
    price: float
    quantity: float
    created_at: datetime = field(default_factory=utc_now)
    status: str = "PENDING"
    order_id: str = ""
