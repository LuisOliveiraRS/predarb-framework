from __future__ import annotations

from math import isfinite
from typing import Any


class ArbitrageCalculator:
    """
    Calcula uma arbitragem binária entre:

    - compra do lado Yes;
    - compra do lado No.

    Existe arbitragem quando:

        yes_price + no_price < 1

    O resultado contém o formato canônico e
    os campos legados utilizados pelo Pipeline.
    """

    @staticmethod
    def _price(
        value: Any,
        field_name: str,
    ) -> float:
        """
        Valida um preço probabilístico.
        """

        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} não "
                "pode ser booleano."
            )

        try:
            price = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve "
                "ser numérico."
            ) from exc

        if not isfinite(price):
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser finito."
            )

        if not 0 <= price <= 1:
            raise ValueError(
                f"O campo {field_name!r} deve "
                "estar entre 0 e 1."
            )

        return price

    @staticmethod
    def _extra_cost(
        value: Any,
    ) -> float:
        """
        Valida um custo adicional absoluto.

        Por padrão, taxas das plataformas ainda
        não são aplicadas automaticamente porque
        o modelo atual não define se fee é taxa
        percentual ou custo por contrato.
        """

        if isinstance(value, bool):
            raise TypeError(
                "extra_cost não pode ser booleano."
            )

        try:
            cost = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                "extra_cost deve ser numérico."
            ) from exc

        if not isfinite(cost) or cost < 0:
            raise ValueError(
                "extra_cost deve ser finito "
                "e não negativo."
            )

        return cost

    def calculate(
        self,
        yes_price: Any,
        no_price: Any,
        *,
        extra_cost: Any = 0.0,
    ) -> dict[str, Any] | None:
        """
        Calcula a oportunidade de arbitragem.
        """

        yes = self._price(
            yes_price,
            "yes_price",
        )

        no = self._price(
            no_price,
            "no_price",
        )

        additional_cost = self._extra_cost(
            extra_cost
        )

        gross_cost = yes + no

        total_cost = (
            gross_cost
            + additional_cost
        )

        if total_cost >= 1:
            return None

        profit = 1.0 - total_cost

        roi = (
            profit
            / total_cost
            * 100
            if total_cost > 0
            else 0.0
        )

        rounded_yes = round(
            yes,
            6,
        )

        rounded_no = round(
            no,
            6,
        )

        rounded_cost = round(
            total_cost,
            6,
        )

        rounded_profit = round(
            profit,
            6,
        )

        rounded_roi = round(
            roi,
            4,
        )

        return {
            # Formato canônico
            "yes_price": rounded_yes,
            "no_price": rounded_no,
            "cost": rounded_cost,
            "profit": rounded_profit,
            "roi": rounded_roi,
            "edge": rounded_profit,
            "spread": rounded_profit,
            "expected_return": rounded_profit,
            "breakeven": rounded_cost,

            # Diagnóstico
            "gross_cost": round(
                gross_cost,
                6,
            ),
            "extra_cost": round(
                additional_cost,
                6,
            ),

            # Formato legado
            "prices": {
                "yes": rounded_yes,
                "no": rounded_no,
            },
            "stake": {
                "yes": rounded_yes,
                "no": rounded_no,
                "total": rounded_cost,
            },
        }


calculator = ArbitrageCalculator()