from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """Retorna o instante atual como datetime UTC com timezone."""

    return datetime.now(timezone.utc)
