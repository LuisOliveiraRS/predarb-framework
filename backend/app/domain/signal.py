from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from app.utils.time import utc_now


@dataclass
class Signal:
    question: str
    action: str
    confidence: float
    created_at: datetime = field(default_factory=utc_now)
