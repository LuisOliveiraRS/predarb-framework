from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


_MISSING = object()


class EnrichStage(PipelineStage):
    """
    Enriquece oportunidades com campos canônicos.

    Campos derivados quando ausentes:

    - yes_price;
    - no_price;
    - cost;
    - edge;
    - spread;
    - expected_return;
    - breakeven;
    - confidence;
    - match_score;
    - created_at;
    - score;
    - approved.

    Os campos originais são preservados.
    """

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = _MISSING,
    ) -> Any:
        if isinstance(target, Mapping):
            if field_name in target:
                return target[field_name]

        elif target is not None and hasattr(
            target,
            field_name,
        ):
            return getattr(
                target,
                field_name,
            )

        if default is not _MISSING:
            return default

        raise ValueError(
            f"Campo não encontrado: {field_name}."
        )

    @classmethod
    def _read_nested(
        cls,
        target: Any,
        parent: str,
        child: str,
        default: Any = None,
    ) -> Any:
        parent_value = cls._read_field(
            target,
            parent,
            None,
        )

        if parent_value is None:
            return default

        return cls._read_field(
            parent_value,
            child,
            default,
        )

    @staticmethod
    def _number(
        value: Any,
        default: float = 0.0,
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
        """
        Cria uma cópia segura da oportunidade.
        """

        if isinstance(opportunity, Mapping):
            return dict(
                opportunity,
            )

        return copy(
            opportunity,
        )

    @staticmethod
    def _set_field(
        target: Any,
        field_name: str,
        value: Any,
    ) -> None:
        """
        Define um campo em dicionário ou objeto.

        Campos inexistentes em objetos com slots são
        armazenados em metadata, quando disponível.
        """

        if isinstance(target, dict):
            target[field_name] = value
            return

        if hasattr(target, field_name):
            setattr(
                target,
                field_name,
                value,
            )
            return

        metadata = getattr(
            target,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata[field_name] = value

    @classmethod
    def _confidence(
        cls,
        opportunity: Any,
    ) -> float:
        """
        Recupera uma confiança entre 0 e 100.
        """

        confidence = cls._read_field(
            opportunity,
            "confidence",
            None,
        )

        if confidence is None:
            confidence = cls._read_field(
                opportunity,
                "similarity",
                None,
            )

        if confidence is None:
            confidence = cls._read_field(
                opportunity,
                "match_score",
                100.0,
            )

        confidence_number = cls._number(
            confidence,
            100.0,
        )

        if 0 <= confidence_number <= 1:
            confidence_number *= 100

        return round(
            min(
                100.0,
                max(
                    0.0,
                    confidence_number,
                ),
            ),
            2,
        )

    def enrich_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        """
        Enriquece uma única oportunidade.
        """

        result = self._clone(
            opportunity,
        )

        yes_price = self._number(
            self._read_field(
                opportunity,
                "yes_price",
                self._read_nested(
                    opportunity,
                    "prices",
                    "yes",
                    0.0,
                ),
            )
        )

        no_price = self._number(
            self._read_field(
                opportunity,
                "no_price",
                self._read_nested(
                    opportunity,
                    "prices",
                    "no",
                    0.0,
                ),
            )
        )

        cost = self._read_field(
            opportunity,
            "cost",
            None,
        )

        if cost is None:
            cost = self._read_nested(
                opportunity,
                "stake",
                "total",
                None,
            )

        if cost is None:
            cost = yes_price + no_price

        cost = self._number(
            cost,
            yes_price + no_price,
        )

        profit = self._number(
            self._read_field(
                opportunity,
                "profit",
                max(
                    0.0,
                    1.0 - cost,
                ),
            )
        )

        roi = self._read_field(
            opportunity,
            "roi",
            None,
        )

        if roi is None:
            roi = (
                profit / cost * 100
                if cost > 0
                else 0.0
            )

        roi = self._number(
            roi,
        )

        edge = self._number(
            self._read_field(
                opportunity,
                "edge",
                profit,
            )
        )

        spread = self._number(
            self._read_field(
                opportunity,
                "spread",
                abs(
                    1.0 - cost,
                ),
            )
        )

        expected_return = self._number(
            self._read_field(
                opportunity,
                "expected_return",
                profit,
            )
        )

        breakeven = self._number(
            self._read_field(
                opportunity,
                "breakeven",
                cost,
            )
        )

        confidence = self._confidence(
            opportunity,
        )

        match_score = self._number(
            self._read_field(
                opportunity,
                "match_score",
                self._read_field(
                    opportunity,
                    "similarity",
                    confidence,
                ),
            )
        )

        created_at = self._read_field(
            opportunity,
            "created_at",
            None,
        )

        if created_at is None:
            created_at = datetime.now(
                timezone.utc,
            )

        score = self._number(
            self._read_field(
                opportunity,
                "score",
                0.0,
            )
        )

        approved = bool(
            self._read_field(
                opportunity,
                "approved",
                False,
            )
        )

        values = {
            "yes_price": round(
                yes_price,
                6,
            ),
            "no_price": round(
                no_price,
                6,
            ),
            "cost": round(
                cost,
                6,
            ),
            "profit": round(
                profit,
                6,
            ),
            "roi": round(
                roi,
                4,
            ),
            "edge": round(
                edge,
                6,
            ),
            "spread": round(
                spread,
                6,
            ),
            "expected_return": round(
                expected_return,
                6,
            ),
            "breakeven": round(
                breakeven,
                6,
            ),
            "confidence": confidence,
            "match_score": round(
                match_score,
                4,
            ),
            "created_at": created_at,
            "score": score,
            "approved": approved,
        }

        for field_name, value in values.items():
            self._set_field(
                result,
                field_name,
                value,
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

        enriched = [
            self.enrich_opportunity(
                opportunity,
            )
            for opportunity in opportunities
        ]

        context.opportunities = enriched

        context.metadata["enrichment"] = {
            "input": len(opportunities),
            "enriched": len(enriched),
        }

        return context