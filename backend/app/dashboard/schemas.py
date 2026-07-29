from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class DashboardCard(BaseModel):
    title: str
    value: str | int | float
    color: str = "blue"
    key: str | None = None
    unit: str | None = None


class DashboardEvent(BaseModel):
    id: str
    type: str = "info"
    text: str
    time: str
    created_at: datetime
    payload: Any = None


class DashboardResponse(BaseModel):
    status: str = "ONLINE"
    updated_at: datetime

    markets: int = 0
    opportunities: int = 0
    orders: int = 0
    positions: int = 0
    connections: int = 0

    portfolio: float = 0.0
    pnl: float = 0.0
    ai_confidence: float = 0.0

    cards: list[DashboardCard] = Field(default_factory=list)
    events: list[DashboardEvent] = Field(default_factory=list)
    data: dict[str, Any] = Field(default_factory=dict)
    statistics: dict[str, Any] = Field(default_factory=dict)
    diagnostics: dict[str, Any] = Field(default_factory=dict)
