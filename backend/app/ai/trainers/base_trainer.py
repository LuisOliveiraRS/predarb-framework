from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


@dataclass(slots=True)
class TrainingResult:
    """Resultado explícito de treinamento e validação."""

    model: Any
    version: str
    status: str
    feature_names: tuple[str, ...]
    target_name: str
    rows: int
    train_rows: int
    validation_rows: int
    metrics: dict[str, Any] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)
    probability_calibrated: bool = False
    trained_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "status": self.status,
            "feature_names": list(self.feature_names),
            "target_name": self.target_name,
            "rows": self.rows,
            "train_rows": self.train_rows,
            "validation_rows": self.validation_rows,
            "metrics": dict(self.metrics),
            "warnings": list(self.warnings),
            "probability_calibrated": self.probability_calibrated,
            "trained_at": self.trained_at.isoformat(),
        }


class BaseTrainer(ABC):
    """Contrato base para trainers supervisionados."""

    @abstractmethod
    def fit(self, dataframe: Any, **options: Any) -> TrainingResult:
        raise NotImplementedError

    @abstractmethod
    def status(self) -> dict[str, Any]:
        raise NotImplementedError
