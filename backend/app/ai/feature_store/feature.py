from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class Feature:
    """
    Valor individual utilizado por modelos e regras da camada AI.

    O objeto é imutável para impedir que um vetor já registrado seja
    alterado silenciosamente durante uma análise ou treinamento.
    """

    name: str
    value: float
    source: str = "opportunity"
    version: str = "1"
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def __post_init__(self) -> None:
        normalized_name = str(self.name or "").strip()
        if not normalized_name:
            raise ValueError("O nome da feature não pode ser vazio.")

        if isinstance(self.value, bool):
            raise TypeError("O valor da feature não pode ser booleano.")

        try:
            normalized_value = float(self.value)
        except (TypeError, ValueError) as exc:
            raise TypeError("O valor da feature deve ser numérico.") from exc

        if not isfinite(normalized_value):
            raise ValueError("O valor da feature deve ser finito.")

        normalized_source = str(self.source or "opportunity").strip()
        normalized_version = str(self.version or "1").strip()
        normalized_metadata = dict(self.metadata or {})

        created_at = self.created_at
        if created_at.tzinfo is None:
            created_at = created_at.replace(tzinfo=timezone.utc)

        object.__setattr__(self, "name", normalized_name)
        object.__setattr__(self, "value", normalized_value)
        object.__setattr__(self, "source", normalized_source)
        object.__setattr__(self, "version", normalized_version)
        object.__setattr__(self, "metadata", normalized_metadata)
        object.__setattr__(self, "created_at", created_at)

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "value": self.value,
            "source": self.source,
            "version": self.version,
            "metadata": dict(self.metadata),
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Feature":
        payload = dict(data)
        created_at = payload.get("created_at")

        if isinstance(created_at, str):
            payload["created_at"] = datetime.fromisoformat(created_at)

        return cls(**payload)
