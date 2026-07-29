from __future__ import annotations

from collections.abc import Iterable, Mapping
from math import isfinite
from typing import Any


_MISSING = object()


class SignalService:
    """
    Classifica oportunidades de acordo com
    sua pontuação institucional.

    Regras preservadas:

        score >= 90 → STRONG BUY
        score >= 70 → BUY
        score >= 50 → WATCH
        score <  50 → IGNORE
    """

    STRONG_BUY = "STRONG BUY"
    BUY = "BUY"
    WATCH = "WATCH"
    IGNORE = "IGNORE"

    STRONG_BUY_SCORE = 90.0
    BUY_SCORE = 70.0
    WATCH_SCORE = 50.0

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = _MISSING,
    ) -> Any:
        """
        Recupera um campo de dicionário ou objeto.
        """

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
            "Oportunidade sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _to_score(value: Any) -> float:
        """
        Converte e valida a pontuação.
        """

        if isinstance(value, bool):
            raise TypeError(
                "A pontuação não pode ser booleana."
            )

        try:
            score = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                "A pontuação da oportunidade deve "
                "ser numérica."
            ) from exc

        if not isfinite(score):
            raise ValueError(
                "A pontuação da oportunidade deve "
                "ser um número finito."
            )

        return score

    def generate(self, opportunity: Any) -> str:
        """
        Gera o sinal correspondente à oportunidade.

        Preserva a interface pública original.
        """

        if opportunity is None:
            raise ValueError(
                "Não é possível gerar sinal para "
                "uma oportunidade None."
            )

        score = self._to_score(
            self._read_field(
                opportunity,
                "score",
            )
        )

        if score >= self.STRONG_BUY_SCORE:
            return self.STRONG_BUY

        if score >= self.BUY_SCORE:
            return self.BUY

        if score >= self.WATCH_SCORE:
            return self.WATCH

        return self.IGNORE

    def generate_many(
        self,
        opportunities: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> list[str]:
        """
        Gera sinais para múltiplas oportunidades.
        """

        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "Opportunities deve ser uma coleção."
            )

        signals: list[str] = []

        for opportunity in opportunities:
            try:
                signals.append(
                    self.generate(opportunity)
                )

            except (TypeError, ValueError):
                if not ignore_invalid:
                    raise

        return signals

    def distribution(
        self,
        opportunities: Iterable[Any] | None,
        *,
        ignore_invalid: bool = True,
    ) -> dict[str, int]:
        """
        Retorna a distribuição dos sinais.
        """

        result = {
            self.STRONG_BUY: 0,
            self.BUY: 0,
            self.WATCH: 0,
            self.IGNORE: 0,
        }

        signals = self.generate_many(
            opportunities,
            ignore_invalid=ignore_invalid,
        )

        for signal in signals:
            result[signal] += 1

        return result

    classify = generate


signal_service = SignalService()