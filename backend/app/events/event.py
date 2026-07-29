from __future__ import annotations

from typing import Any

from app.utils.time import utc_now


class Event:
    """Evento simples, serializável e com timestamp UTC."""

    def __init__(
        self,
        name: str,
        payload: Any = None,
    ) -> None:
        normalized_name = str(name or "").strip()
        if not normalized_name:
            raise ValueError("O nome do evento não pode ser vazio.")

        self.name = normalized_name
        self.payload = payload
        self.created_at = utc_now()

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "payload": self.payload,
            "created_at": self.created_at.isoformat(),
        }
