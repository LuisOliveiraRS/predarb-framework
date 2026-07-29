from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from math import isfinite
from typing import Any


class PredictionStatus(str, Enum):
    """Estados explícitos produzidos por um predictor."""

    HEURISTIC_ONLY = "HEURISTIC_ONLY"
    MODEL_PREDICTION = "MODEL_PREDICTION"
    MODEL_UNAVAILABLE = "MODEL_UNAVAILABLE"
    INVALID_FEATURES = "INVALID_FEATURES"


@dataclass(slots=True)
class PredictionResult:
    """
    Resultado seguro de inferência.

    ``heuristic_score`` e ``final_score`` são scores de recomendação entre
    zero e um. Eles não são probabilidades calibradas.

    ``model_probability`` somente é preenchida quando um modelo com
    ``predict_proba`` está registrado.
    """

    heuristic_score: float
    final_score: float
    confidence: float
    prediction_status: PredictionStatus

    model_probability: float | None = None
    model_version: str | None = None
    probability_calibrated: bool = False
    feature_coverage: float = 1.0
    recommendation: str = "REVIEW"
    warnings: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    # A camada AI é sempre consultiva.
    advisory_only: bool = True
    execution_authorized: bool = False

    def __post_init__(self) -> None:
        self.heuristic_score = self._unit(self.heuristic_score, "heuristic_score")
        self.final_score = self._unit(self.final_score, "final_score")
        self.confidence = self._unit(self.confidence, "confidence")
        self.feature_coverage = self._unit(
            self.feature_coverage,
            "feature_coverage",
        )

        if self.model_probability is not None:
            self.model_probability = self._unit(
                self.model_probability,
                "model_probability",
            )

        if not isinstance(self.prediction_status, PredictionStatus):
            self.prediction_status = PredictionStatus(str(self.prediction_status))

        self.model_version = (
            str(self.model_version).strip() if self.model_version else None
        )
        self.recommendation = str(self.recommendation or "REVIEW").strip().upper()
        self.warnings = list(dict.fromkeys(str(item) for item in self.warnings))
        self.metadata = dict(self.metadata or {})
        self.advisory_only = True
        self.execution_authorized = False

    @staticmethod
    def _unit(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")

        number = float(value)
        if not isfinite(number):
            raise ValueError(f"{field_name} deve ser finito.")
        if not 0 <= number <= 1:
            raise ValueError(f"{field_name} deve estar entre 0 e 1.")
        return round(number, 10)

    def to_dict(self) -> dict[str, Any]:
        return {
            "heuristic_score": self.heuristic_score,
            "model_probability": self.model_probability,
            "final_score": self.final_score,
            "confidence": self.confidence,
            "model_version": self.model_version,
            "probability_calibrated": self.probability_calibrated,
            "prediction_status": self.prediction_status.value,
            "feature_coverage": self.feature_coverage,
            "recommendation": self.recommendation,
            "warnings": list(self.warnings),
            "metadata": dict(self.metadata),
            "advisory_only": True,
            "execution_authorized": False,
        }

    def __float__(self) -> float:
        """Compatibilidade para consumidores antigos que esperavam um score."""

        return self.final_score

    def __bool__(self) -> bool:
        """O resultado não autoriza execução; bool indica apenas validade."""

        return self.prediction_status is not PredictionStatus.INVALID_FEATURES


class BasePredictor(ABC):
    """Contrato base de predictors consultivos."""

    @abstractmethod
    def predict(self, features: dict[str, float]) -> PredictionResult:
        raise NotImplementedError

    def predict_many(
        self,
        feature_rows: list[dict[str, float]],
    ) -> list[PredictionResult]:
        return [self.predict(features) for features in feature_rows]

    @abstractmethod
    def status(self) -> dict[str, Any]:
        raise NotImplementedError
