from __future__ import annotations

from collections.abc import Mapping
from difflib import SequenceMatcher
from math import isfinite
from typing import Any

from app.market.normalizer import normalizer


class MarketMatcher:
    """
    Verifica se dois mercados representam
    o mesmo evento.

    Aceita:

    - objetos Market;
    - dicionários;
    - objetos compatíveis com o modelo Market.
    """

    MIN_SIMILARITY = 0.82

    def __init__(
        self,
        *,
        min_similarity: float | None = None,
    ) -> None:
        threshold = (
            self.MIN_SIMILARITY
            if min_similarity is None
            else float(min_similarity)
        )

        if (
            not isfinite(threshold)
            or not 0 <= threshold <= 1
        ):
            raise ValueError(
                "min_similarity deve estar "
                "entre 0 e 1."
            )

        self.min_similarity = threshold

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera campos de dicionários
        ou objetos.
        """

        if isinstance(target, Mapping):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @classmethod
    def _question(
        cls,
        market: Any,
    ) -> str:
        """
        Recupera e valida a pergunta
        de um mercado.
        """

        question = cls._read_field(
            market,
            "question",
            None,
        )

        if not isinstance(question, str):
            raise TypeError(
                "O mercado deve possuir uma "
                "pergunta textual."
            )

        normalized_question = question.strip()

        if not normalized_question:
            raise ValueError(
                "A pergunta do mercado não "
                "pode ser vazia."
            )

        return normalized_question

    @staticmethod
    def _normalize_question(
        question: str,
    ) -> str:
        """
        Normaliza uma pergunta antes
        da comparação.
        """

        normalized = normalizer.normalize(
            question
        )

        if not isinstance(normalized, str):
            return ""

        return normalized.strip()

    def similarity(
        self,
        question_a: str,
        question_b: str,
    ) -> float:
        """
        Calcula a similaridade entre
        duas perguntas.
        """

        if not isinstance(question_a, str):
            raise TypeError(
                "question_a deve ser uma string."
            )

        if not isinstance(question_b, str):
            raise TypeError(
                "question_b deve ser uma string."
            )

        normalized_a = self._normalize_question(
            question_a
        )

        normalized_b = self._normalize_question(
            question_b
        )

        if not normalized_a or not normalized_b:
            return 0.0

        if normalized_a == normalized_b:
            return 1.0

        score = SequenceMatcher(
            None,
            normalized_a,
            normalized_b,
        ).ratio()

        return round(
            min(
                1.0,
                max(
                    0.0,
                    float(score),
                ),
            ),
            6,
        )

    def compare(
        self,
        market_a: Any,
        market_b: Any,
    ) -> dict[str, Any]:
        """
        Compara dois mercados.
        """

        question_a = self._question(
            market_a
        )

        question_b = self._question(
            market_b
        )

        similarity = self.similarity(
            question_a,
            question_b,
        )

        return {
            "matched": (
                similarity
                >= self.min_similarity
            ),
            "similarity": similarity,
            "threshold": self.min_similarity,
            "question_a": question_a,
            "question_b": question_b,
        }

    def is_match(
        self,
        market_a: Any,
        market_b: Any,
    ) -> bool:
        """
        Retorna somente o resultado booleano.
        """

        return bool(
            self.compare(
                market_a,
                market_b,
            )["matched"]
        )

    def match(
        self,
        market_a: Any,
        market_b: Any,
    ) -> bool:
        """
        Alias preservado para a implementação
        existente em app.market.matcher.
        """

        return self.is_match(
            market_a,
            market_b,
        )


market_matcher = MarketMatcher()