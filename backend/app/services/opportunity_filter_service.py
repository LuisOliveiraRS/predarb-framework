from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


_MISSING = object()


class OpportunityFilterService:
    """
    Aplica os limites mínimos de viabilidade
    financeira sobre oportunidades.

    O ROI é tratado em pontos percentuais.

    Exemplos:

        ROI 1.0  = 1%
        ROI 10.0 = 10%
    """

    MIN_ROI = 0.01
    MIN_PROFIT = 0.25

    @staticmethod
    def _read_field(
        opportunity: Any,
        field_name: str,
        default: Any = _MISSING,
    ) -> Any:
        """
        Recupera campos de dicionários ou objetos.
        """

        if isinstance(
            opportunity,
            Mapping,
        ):
            if field_name in opportunity:
                return opportunity[field_name]

        elif hasattr(
            opportunity,
            field_name,
        ):
            return getattr(
                opportunity,
                field_name,
            )

        if default is not _MISSING:
            return default

        raise ValueError(
            "Oportunidade sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _to_number(
        value: Any,
        field_name: str,
    ) -> float:
        """
        Converte um valor financeiro em float.
        """

        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"O campo {field_name!r} não pode "
                "ser booleano."
            )

        try:
            return float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve "
                "ser numérico."
            ) from exc

    def is_approved(
        self,
        opportunity: Any,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
    ) -> bool:
        """
        Verifica uma única oportunidade.
        """

        if opportunity is None:
            return False

        resolved_min_roi = (
            self.MIN_ROI
            if min_roi is None
            else float(min_roi)
        )

        resolved_min_profit = (
            self.MIN_PROFIT
            if min_profit is None
            else float(min_profit)
        )

        roi = self._to_number(
            self._read_field(
                opportunity,
                "roi",
            ),
            "roi",
        )

        profit = self._to_number(
            self._read_field(
                opportunity,
                "profit",
            ),
            "profit",
        )

        return (
            roi >= resolved_min_roi
            and profit >= resolved_min_profit
        )

    def filter(
        self,
        opportunities: Iterable[Any] | None,
        *,
        min_roi: float | None = None,
        min_profit: float | None = None,
        ignore_invalid: bool = True,
    ) -> list[Any]:
        """
        Filtra uma coleção de oportunidades.

        Quando ``ignore_invalid`` for True,
        oportunidades incompletas são descartadas
        sem interromper todo o processamento.
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

        approved: list[Any] = []

        for opportunity in opportunities:
            try:
                if self.is_approved(
                    opportunity,
                    min_roi=min_roi,
                    min_profit=min_profit,
                ):
                    approved.append(
                        opportunity,
                    )

            except (
                TypeError,
                ValueError,
            ):
                if not ignore_invalid:
                    raise

        return approved


opportunity_filter_service = (
    OpportunityFilterService()
)