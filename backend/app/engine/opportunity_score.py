from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.engine.opportunity_ranker import (
    OpportunityRanker,
    opportunity_ranker,
)


class OpportunityScore:
    """
    Calcula o score canônico de uma oportunidade.

    Os campos abaixo passam a possuir o mesmo valor:

        score
        opportunity_score

    opportunity_score é mantido somente para
    compatibilidade com módulos antigos.
    """

    def __init__(
        self,
        *,
        ranker: OpportunityRanker | None = None,
    ) -> None:
        self.ranker = ranker or opportunity_ranker

    @staticmethod
    def _set_legacy_alias(
        opportunity: Any,
        score: float,
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["opportunity_score"] = score
            return

        if hasattr(opportunity, "opportunity_score"):
            setattr(
                opportunity,
                "opportunity_score",
                score,
            )
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["opportunity_score"] = score

    def score(
        self,
        opportunity: Any,
    ) -> float:
        """
        Retorna somente o valor numérico.
        """

        return self.ranker.calculate_score(
            opportunity
        )

    def calculate(
        self,
        opportunity: Any,
    ) -> Any:
        """
        Retorna uma cópia da oportunidade
        contendo o score calculado.
        """

        result = self.ranker.rank_one(
            opportunity
        )

        score = self.ranker.calculate_score(
            result
        )

        self._set_legacy_alias(
            result,
            score,
        )

        return result

    def calculate_many(
        self,
        opportunities: Any,
    ) -> list[Any]:
        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            Mapping,
        ):
            items = [opportunities]

        elif isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "opportunities deve ser uma coleção."
            )

        elif isinstance(
            opportunities,
            Iterable,
        ):
            items = list(opportunities)

        else:
            items = [opportunities]

        return [
            self.calculate(opportunity)
            for opportunity in items
        ]


opportunity_score = OpportunityScore()