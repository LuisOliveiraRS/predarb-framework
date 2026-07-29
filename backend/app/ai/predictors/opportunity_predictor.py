from __future__ import annotations

from collections.abc import Mapping
from math import isfinite, log1p
from typing import Any

import pandas as pd

from app.ai.feature_store.feature_builder import FeatureBuilder
from app.ai.predictors.base_predictor import (
    BasePredictor,
    PredictionResult,
    PredictionStatus,
)


class OpportunityPredictor(BasePredictor):
    """
    Predictor consultivo de oportunidades.

    Sem modelo treinado, produz somente um score heurístico explícito.
    Quando um modelo é registrado, expõe separadamente a probabilidade do
    modelo e um score final combinado. Nenhum resultado aprova execução.
    """

    DEFAULT_MODEL_WEIGHT = 0.75

    def __init__(
        self,
        *,
        model: Any = None,
        model_version: str | None = None,
        probability_calibrated: bool = False,
        model_weight: float = DEFAULT_MODEL_WEIGHT,
        feature_names: tuple[str, ...] | None = None,
    ) -> None:
        self.feature_names = tuple(feature_names or FeatureBuilder.FEATURE_NAMES)
        self.model = model
        self.model_version = model_version
        self.probability_calibrated = bool(probability_calibrated)
        self.model_weight = self._unit(model_weight, "model_weight")
        self.last_result: PredictionResult | None = None

    @staticmethod
    def _unit(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        number = float(value)
        if not isfinite(number) or not 0 <= number <= 1:
            raise ValueError(f"{field_name} deve estar entre 0 e 1.")
        return number

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, float(value)))

    @classmethod
    def _normalized_number(cls, value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"A feature {field_name!r} não pode ser booleana.")
        number = float(value)
        if not isfinite(number):
            raise ValueError(f"A feature {field_name!r} deve ser finita.")
        return number

    def _normalize_features(
        self,
        features: Mapping[str, Any],
    ) -> tuple[dict[str, float], float, list[str]]:
        if not isinstance(features, Mapping):
            raise TypeError("features deve ser um mapping.")

        normalized: dict[str, float] = {}
        warnings: list[str] = []
        present = 0

        for name in self.feature_names:
            if name not in features or features[name] is None:
                normalized[name] = 0.0
                warnings.append(f"FEATURE_MISSING:{name}")
                continue

            try:
                normalized[name] = self._normalized_number(features[name], name)
                present += 1
            except (TypeError, ValueError):
                normalized[name] = 0.0
                warnings.append(f"FEATURE_INVALID:{name}")

        coverage = present / len(self.feature_names) if self.feature_names else 0.0
        return normalized, round(coverage, 10), warnings

    def heuristic_score(self, features: Mapping[str, Any]) -> float:
        """Retorna um score heurístico entre 0 e 1; não é probabilidade."""

        values, _, _ = self._normalize_features(features)

        roi = self._clamp(values["roi"] / 25.0)
        edge = self._clamp(values["edge"] / 0.25)
        confidence = self._clamp(values["confidence"])
        match_score = self._clamp(values["match_score"])
        risk_quality = 1.0 - self._clamp(values["risk_score"] / 100.0)
        liquidity = self._clamp(log1p(max(0.0, values["liquidity"])) / log1p(10_000.0))
        spread_quality = 1.0 - self._clamp(abs(values["spread"]) / 0.05)
        slippage_quality = 1.0 - self._clamp(
            abs(values["slippage_rate"]) / 0.03
        )

        score = (
            roi * 0.20
            + edge * 0.18
            + confidence * 0.15
            + match_score * 0.15
            + risk_quality * 0.10
            + liquidity * 0.10
            + spread_quality * 0.07
            + slippage_quality * 0.05
        )
        return round(self._clamp(score), 10)

    def set_model(
        self,
        model: Any,
        *,
        version: str,
        probability_calibrated: bool = False,
    ) -> None:
        if model is None:
            raise ValueError("model não pode ser None.")
        if not str(version or "").strip():
            raise ValueError("version é obrigatória.")

        self.model = model
        self.model_version = str(version).strip()
        self.probability_calibrated = bool(probability_calibrated)

    def clear_model(self) -> None:
        self.model = None
        self.model_version = None
        self.probability_calibrated = False

    def _model_probability(self, values: dict[str, float]) -> float:
        if self.model is None:
            raise RuntimeError("MODEL_UNAVAILABLE")

        predict_proba = getattr(self.model, "predict_proba", None)
        if not callable(predict_proba):
            raise TypeError("MODEL_WITHOUT_PREDICT_PROBA")

        row = pd.DataFrame(
            [[values[name] for name in self.feature_names]],
            columns=self.feature_names,
            dtype=float,
        )
        probabilities = predict_proba(row)
        if len(probabilities) != 1:
            raise ValueError("MODEL_INVALID_PROBABILITY_SHAPE")

        classes = list(getattr(self.model, "classes_", []))
        if 1 in classes:
            positive_index = classes.index(1)
        elif True in classes:
            positive_index = classes.index(True)
        elif len(probabilities[0]) == 2:
            positive_index = 1
        else:
            raise ValueError("MODEL_POSITIVE_CLASS_NOT_FOUND")

        probability = float(probabilities[0][positive_index])
        return self._unit(probability, "model_probability")

    @staticmethod
    def _recommendation(score: float) -> str:
        if score >= 0.70:
            return "POSITIVE"
        if score <= 0.40:
            return "NEGATIVE"
        return "REVIEW"

    def predict(self, features: dict[str, float]) -> PredictionResult:
        values, coverage, warnings = self._normalize_features(features)
        heuristic = self.heuristic_score(values)

        if coverage == 0:
            result = PredictionResult(
                heuristic_score=heuristic,
                final_score=heuristic,
                confidence=0.0,
                prediction_status=PredictionStatus.INVALID_FEATURES,
                feature_coverage=coverage,
                recommendation="REVIEW",
                warnings=warnings or ["FEATURE_VECTOR_EMPTY"],
                metadata={"feature_names": list(self.feature_names)},
            )
            self.last_result = result
            return result

        model_probability: float | None = None
        status = PredictionStatus.HEURISTIC_ONLY

        if self.model is not None:
            try:
                model_probability = self._model_probability(values)
                status = PredictionStatus.MODEL_PREDICTION
            except Exception as exc:
                warnings.append(str(exc))
                status = PredictionStatus.MODEL_UNAVAILABLE

        if model_probability is None:
            final_score = heuristic
            decision_strength = abs(heuristic - 0.5) * 2
            confidence = coverage * (0.5 + decision_strength * 0.5)
        else:
            final_score = (
                model_probability * self.model_weight
                + heuristic * (1.0 - self.model_weight)
            )
            model_certainty = abs(model_probability - 0.5) * 2
            confidence = coverage * (0.5 + model_certainty * 0.5)

        result = PredictionResult(
            heuristic_score=heuristic,
            model_probability=model_probability,
            final_score=round(self._clamp(final_score), 10),
            confidence=round(self._clamp(confidence), 10),
            model_version=self.model_version if model_probability is not None else None,
            probability_calibrated=(
                self.probability_calibrated if model_probability is not None else False
            ),
            prediction_status=status,
            feature_coverage=coverage,
            recommendation=self._recommendation(final_score),
            warnings=warnings,
            metadata={
                "feature_names": list(self.feature_names),
                "model_weight": self.model_weight if model_probability is not None else 0.0,
                "heuristic_weight": (
                    1.0 - self.model_weight if model_probability is not None else 1.0
                ),
            },
        )
        self.last_result = result
        return result

    def predict_score(self, features: dict[str, float]) -> float:
        """Compatibilidade numérica com a implementação anterior."""

        return self.predict(features).final_score

    def status(self) -> dict[str, Any]:
        return {
            "model_loaded": self.model is not None,
            "model_version": self.model_version,
            "probability_calibrated": self.probability_calibrated,
            "model_weight": self.model_weight,
            "feature_names": list(self.feature_names),
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "advisory_only": True,
            "execution_authorized": False,
        }


opportunity_predictor = OpportunityPredictor()
