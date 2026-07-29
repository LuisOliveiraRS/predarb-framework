from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any


class FeatureBuilder:
    """
    Extrai o vetor canônico de uma oportunidade.

    O builder aceita dicionários e objetos, inclusive o modelo Opportunity.
    Nenhuma feature é inventada: campos ausentes são registrados no relatório
    e recebem zero apenas quando strict=False.
    """

    FEATURE_NAMES = (
        "roi",
        "profit",
        "spread",
        "edge",
        "confidence",
        "match_score",
        "risk_score",
        "liquidity",
        "slippage_rate",
    )

    def __init__(self) -> None:
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field, default)

        if target is None:
            return default

        return getattr(target, field, default)

    @classmethod
    def _nested(
        cls,
        target: Any,
        parent: str,
        child: str,
        default: Any = None,
    ) -> Any:
        return cls._read(
            cls._read(target, parent, None),
            child,
            default,
        )

    @staticmethod
    def _number(value: Any, field: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"A feature {field!r} não pode ser booleana.")

        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"A feature {field!r} deve ser numérica.") from exc

        if not isfinite(number):
            raise ValueError(f"A feature {field!r} deve ser finita.")

        return number

    @classmethod
    def _unit_interval(cls, value: Any, field: str) -> float:
        number = cls._number(value, field)

        if 1 < number <= 100:
            number /= 100

        if not 0 <= number <= 1:
            raise ValueError(
                f"A feature {field!r} deve estar entre 0 e 1 "
                "ou entre 0 e 100."
            )

        return number

    @classmethod
    def _extract_raw(cls, opportunity: Any) -> dict[str, Any]:
        risk_score = cls._nested(opportunity, "risk", "score", None)
        if risk_score is None:
            risk_score = cls._read(opportunity, "risk_score", None)

        liquidity = cls._nested(opportunity, "liquidity", "available", None)
        if liquidity is None:
            liquidity = cls._nested(opportunity, "liquidity", "total", None)
        if liquidity is None:
            liquidity = cls._read(opportunity, "available_liquidity", None)

        slippage_rate = cls._nested(opportunity, "slippage", "rate", None)
        if slippage_rate is None:
            slippage_rate = cls._read(opportunity, "slippage_rate", None)

        return {
            "roi": cls._read(opportunity, "roi", None),
            "profit": cls._read(opportunity, "profit", None),
            "spread": cls._read(opportunity, "spread", None),
            "edge": cls._read(opportunity, "edge", None),
            "confidence": cls._read(opportunity, "confidence", None),
            "match_score": cls._read(opportunity, "match_score", None),
            "risk_score": risk_score,
            "liquidity": liquidity,
            "slippage_rate": slippage_rate,
        }

    def build(
        self,
        opportunity: Any,
        *,
        strict: bool = False,
    ) -> dict[str, float]:
        if opportunity is None:
            raise ValueError("opportunity não pode ser None.")

        raw = self._extract_raw(opportunity)
        features: dict[str, float] = {}
        missing: list[str] = []
        invalid: dict[str, str] = {}

        for name in self.FEATURE_NAMES:
            value = raw.get(name)

            if value is None:
                missing.append(name)
                features[name] = 0.0
                continue

            try:
                if name in {"confidence", "match_score"}:
                    features[name] = self._unit_interval(value, name)
                else:
                    features[name] = self._number(value, name)
            except (TypeError, ValueError) as exc:
                invalid[name] = str(exc)
                features[name] = 0.0

        self.last_report = {
            "feature_names": list(self.FEATURE_NAMES),
            "missing": missing,
            "invalid": invalid,
            "strict": bool(strict),
            "valid": not missing and not invalid,
        }

        if strict and (missing or invalid):
            details: list[str] = []
            if missing:
                details.append("ausentes: " + ", ".join(missing))
            if invalid:
                details.append("inválidas: " + ", ".join(invalid))

            raise ValueError("Vetor de features inválido; " + "; ".join(details))

        return features

    def build_many(
        self,
        opportunities: Iterable[Any],
        *,
        strict: bool = False,
    ) -> list[dict[str, float]]:
        if isinstance(opportunities, (str, bytes, Mapping)):
            raise TypeError("opportunities deve ser uma coleção.")

        return [
            self.build(opportunity, strict=strict)
            for opportunity in opportunities
        ]


feature_builder = FeatureBuilder()
