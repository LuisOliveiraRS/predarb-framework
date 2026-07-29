from __future__ import annotations

from app.positions.position_status import PositionStatus
from app.utils.time import utc_now


class PositionCloser:
    """Fecha posições de forma idempotente."""

    def close(self, position):
        position.status = PositionStatus.CLOSED
        if getattr(position, "closed_at", None) is None:
            position.closed_at = utc_now()
        return position


position_closer = PositionCloser()
