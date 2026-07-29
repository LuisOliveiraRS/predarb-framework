from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class OrderResult:
    """Resultado genérico de uma operação do OMS.

    Preserva os campos legados ``order``, ``success`` e ``message`` e
    acrescenta um contrato serializável para as camadas seguintes.
    """

    order: Any
    success: bool
    message: str = ""
    status: str = ""
    data: Any = None
    error: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        self.success = bool(self.success)
        self.message = str(self.message or "").strip()
        self.status = str(
            self.status or ("SUCCESS" if self.success else "FAILED")
        ).strip().upper()
        self.error = None if self.error is None else str(self.error)
        self.metadata = dict(self.metadata or {})
        if self.created_at.tzinfo is None:
            self.created_at = self.created_at.replace(tzinfo=timezone.utc)

    @property
    def order_id(self) -> str:
        return str(getattr(self.order, "id", "") or "")

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "success": self.success,
            "status": self.status,
            "message": self.message,
            "data": self.data,
            "error": self.error,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }
