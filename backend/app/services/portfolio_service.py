from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


_MISSING = object()


class PortfolioService:
    """
    Serviço de cálculos básicos de portfólio.

    O método exposure() preserva o comportamento
    original e calcula a exposição líquida:

        soma das quantidades com seus sinais.

    Exemplo:

        posição comprada:  +10
        posição vendida:    -4
        exposição líquida:   6
    """

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
            "Posição sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _to_decimal(
        value: Any,
        field_name: str,
    ) -> Decimal:
        """
        Converte valores numéricos para Decimal.
        """

        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} não pode "
                "ser booleano."
            )

        try:
            number = Decimal(
                str(value)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve "
                "ser numérico."
            ) from exc

        if not number.is_finite():
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser um número finito."
            )

        return number

    def _quantities(
        self,
        positions: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> list[Decimal]:
        """
        Extrai as quantidades das posições.
        """

        if positions is None:
            return []

        if isinstance(
            positions,
            (str, bytes),
        ):
            raise TypeError(
                "Positions deve ser uma coleção."
            )

        quantities: list[Decimal] = []

        for position in positions:
            try:
                quantity = self._read_field(
                    position,
                    "quantity",
                )

                quantities.append(
                    self._to_decimal(
                        quantity,
                        "quantity",
                    )
                )

            except (TypeError, ValueError):
                if not ignore_invalid:
                    raise

        return quantities

    def exposure(
        self,
        positions: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> float:
        """
        Calcula a exposição líquida do portfólio.

        Preserva a interface pública original.
        """

        quantities = self._quantities(
            positions,
            ignore_invalid=ignore_invalid,
        )

        total = sum(
            quantities,
            Decimal("0"),
        )

        return round(
            float(total),
            2,
        )

    def gross_exposure(
        self,
        positions: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> float:
        """
        Calcula a exposição bruta.

        A exposição bruta soma os valores absolutos
        das quantidades.
        """

        quantities = self._quantities(
            positions,
            ignore_invalid=ignore_invalid,
        )

        total = sum(
            (
                abs(quantity)
                for quantity in quantities
            ),
            Decimal("0"),
        )

        return round(
            float(total),
            2,
        )

    def summary(
        self,
        positions: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> dict[str, Any]:
        """
        Retorna um resumo básico das posições.
        """

        quantities = self._quantities(
            positions,
            ignore_invalid=ignore_invalid,
        )

        net = sum(
            quantities,
            Decimal("0"),
        )

        gross = sum(
            (
                abs(quantity)
                for quantity in quantities
            ),
            Decimal("0"),
        )

        long_exposure = sum(
            (
                quantity
                for quantity in quantities
                if quantity > 0
            ),
            Decimal("0"),
        )

        short_exposure = sum(
            (
                abs(quantity)
                for quantity in quantities
                if quantity < 0
            ),
            Decimal("0"),
        )

        return {
            "positions": len(quantities),
            "net_exposure": round(
                float(net),
                2,
            ),
            "gross_exposure": round(
                float(gross),
                2,
            ),
            "long_exposure": round(
                float(long_exposure),
                2,
            ),
            "short_exposure": round(
                float(short_exposure),
                2,
            ),
        }


portfolio_service = PortfolioService()