from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from math import isfinite
from typing import Any

from app.engine.models import RiskResult
from app.pipeline.pipeline_stage import PipelineStage


class RiskStage(PipelineStage):
    """
    Calcula o risco das oportunidades.

    Critérios preservados:

    ROI:
        >= 30 → +5
        >= 20 → +15
        >= 10 → +30
        <  10 → +45

    Spread:
        <= 0,02 → +5
        <= 0,05 → +15
        >  0,05 → +30

    Confiança:
        penalidade de 20% sobre a diferença
        entre 100 e a confiança.

    Classificação:

        score <= 20 → LOW
        score <= 45 → MEDIUM
        score >  45 → HIGH
    """

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(target, Mapping):
            return target.get(
                field_name,
                default,
            )

        return getattr(
            target,
            field_name,
            default,
        )

    @staticmethod
    def _number(
        value: Any,
        default: float,
    ) -> float:
        if value is None or isinstance(
            value,
            bool,
        ):
            return float(
                default,
            )

        try:
            number = float(
                value,
            )

        except (TypeError, ValueError):
            return float(
                default,
            )

        if not isfinite(number):
            return float(
                default,
            )

        return number

    @staticmethod
    def _clone(
        opportunity: Any,
    ) -> Any:
        if isinstance(opportunity, Mapping):
            return dict(
                opportunity,
            )

        return copy(
            opportunity,
        )

    @staticmethod
    def _set_risk(
        target: Any,
        *,
        score: float,
        level: str,
        reasons: list[str],
    ) -> None:
        if isinstance(target, dict):
            target["risk"] = {
                "score": score,
                "level": level,
                "reasons": reasons,
            }

            return

        if hasattr(target, "risk"):
            setattr(
                target,
                "risk",
                RiskResult(
                    score=score,
                    level=level,
                    reasons=reasons,
                ),
            )

            return

        metadata = getattr(
            target,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["risk"] = {
                "score": score,
                "level": level,
                "reasons": reasons,
            }

    def analyze_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        result = self._clone(
            opportunity,
        )

        roi = self._number(
            self._read_field(
                opportunity,
                "roi",
                0.0,
            ),
            0.0,
        )

        spread = abs(
            self._number(
                self._read_field(
                    opportunity,
                    "spread",
                    0.0,
                ),
                0.0,
            )
        )

        confidence = self._number(
            self._read_field(
                opportunity,
                "confidence",
                100.0,
            ),
            100.0,
        )

        confidence = min(
            100.0,
            max(
                0.0,
                confidence,
            ),
        )

        risk_score = 0.0
        reasons: list[str] = []

        if roi >= 30:
            risk_score += 5
            reasons.append(
                "ROI muito alto.",
            )

        elif roi >= 20:
            risk_score += 15
            reasons.append(
                "ROI alto.",
            )

        elif roi >= 10:
            risk_score += 30
            reasons.append(
                "ROI moderado.",
            )

        else:
            risk_score += 45
            reasons.append(
                "ROI baixo.",
            )

        if spread <= 0.02:
            risk_score += 5
            reasons.append(
                "Spread baixo.",
            )

        elif spread <= 0.05:
            risk_score += 15
            reasons.append(
                "Spread moderado.",
            )

        else:
            risk_score += 30
            reasons.append(
                "Spread elevado.",
            )

        confidence_penalty = (
            100.0 - confidence
        ) * 0.20

        risk_score += confidence_penalty

        if confidence_penalty > 0:
            reasons.append(
                "Penalidade por confiança "
                f"de {confidence:.2f}%.",
            )

        risk_score = round(
            min(
                100.0,
                max(
                    0.0,
                    risk_score,
                ),
            ),
            2,
        )

        if risk_score <= 20:
            level = "LOW"

        elif risk_score <= 45:
            level = "MEDIUM"

        else:
            level = "HIGH"

        self._set_risk(
            result,
            score=risk_score,
            level=level,
            reasons=reasons,
        )

        return result

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or [],
        )

        analyzed = [
            self.analyze_opportunity(
                opportunity,
            )
            for opportunity in opportunities
        ]

        context.opportunities = analyzed

        levels = {
            "LOW": 0,
            "MEDIUM": 0,
            "HIGH": 0,
        }

        for opportunity in analyzed:
            risk = self._read_field(
                opportunity,
                "risk",
                {},
            )

            level = self._read_field(
                risk,
                "level",
                "HIGH",
            )

            if level in levels:
                levels[level] += 1

        context.metadata["risk"] = {
            "analyzed": len(analyzed),
            "levels": levels,
        }

        return context