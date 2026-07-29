from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class StakeStage(PipelineStage):
    """
    Calcula a distribuição da stake entre os lados
    Yes e No sem alterar a oportunidade original.

    A distribuição equaliza o retorno bruto dos dois
    lados da arbitragem.
    """

    def __init__(
        self,
        *,
        bankroll: float = 1_000.0,
        strict: bool = False,
    ) -> None:
        self.bankroll = self._positive_number(
            bankroll,
            "bankroll",
        )

        self.strict = bool(strict)

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

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
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

        return cls._read_field(
            parent_value,
            child,
            default,
        )

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
    ) -> float:
        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if not isfinite(number):
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser finito."
            )

        return number

    @classmethod
    def _positive_number(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        number = cls._number(
            value,
            field_name,
        )

        if number <= 0:
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser maior que zero."
            )

        return number

    @classmethod
    def _prices(
        cls,
        opportunity: Any,
    ) -> tuple[float, float]:
        yes_price = cls._read_field(
            opportunity,
            "yes_price",
            None,
        )

        if yes_price is None:
            yes_price = cls._read_nested(
                opportunity,
                "prices",
                "yes",
                None,
            )

        no_price = cls._read_field(
            opportunity,
            "no_price",
            None,
        )

        if no_price is None:
            no_price = cls._read_nested(
                opportunity,
                "prices",
                "no",
                None,
            )

        yes = cls._positive_number(
            yes_price,
            "yes_price",
        )

        no = cls._positive_number(
            no_price,
            "no_price",
        )

        if yes > 1 or no > 1:
            raise ValueError(
                "yes_price e no_price devem "
                "estar entre 0 e 1."
            )

        return yes, no

    @classmethod
    def _set_stake(
        cls,
        opportunity: Any,
        stake: dict[str, float],
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["stake"] = stake
            return

        current_stake = getattr(
            opportunity,
            "stake",
            None,
        )

        if current_stake is not None:
            if hasattr(
                current_stake,
                "amount",
            ):
                current_stake.amount = (
                    stake["total"]
                )

            if hasattr(
                current_stake,
                "expected_profit",
            ):
                current_stake.expected_profit = (
                    stake["guaranteed_profit"]
                )

            if hasattr(
                current_stake,
                "bankroll_percentage",
            ):
                current_stake.bankroll_percentage = (
                    100.0
                )

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["stake"] = dict(
                stake,
            )

    def calculate_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        result = deepcopy(
            opportunity,
        )

        yes_price, no_price = self._prices(
            opportunity,
        )

        total_price = (
            yes_price
            + no_price
        )

        if total_price <= 0:
            raise ValueError(
                "A soma dos preços deve "
                "ser maior que zero."
            )

        allocated_bankroll = self._read_field(
            opportunity,
            "stake_bankroll",
            self.bankroll,
        )

        allocated_bankroll = (
            self._positive_number(
                allocated_bankroll,
                "stake_bankroll",
            )
        )

        yes_stake = (
            allocated_bankroll
            * yes_price
            / total_price
        )

        no_stake = (
            allocated_bankroll
            * no_price
            / total_price
        )

        guaranteed_return = min(
            yes_stake / yes_price,
            no_stake / no_price,
        )

        guaranteed_profit = (
            guaranteed_return
            - allocated_bankroll
        )

        stake = {
            "bankroll": round(
                allocated_bankroll,
                2,
            ),
            "total": round(
                yes_stake + no_stake,
                2,
            ),
            "yes": round(
                yes_stake,
                2,
            ),
            "no": round(
                no_stake,
                2,
            ),
            "guaranteed_return": round(
                guaranteed_return,
                2,
            ),
            "guaranteed_profit": round(
                guaranteed_profit,
                2,
            ),
        }

        self._set_stake(
            result,
            stake,
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

        calculated: list[Any] = []
        invalid: list[dict[str, Any]] = []

        for index, opportunity in enumerate(
            opportunities,
        ):
            try:
                calculated.append(
                    self.calculate_opportunity(
                        opportunity,
                    )
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                invalid.append(
                    {
                        "index": index,
                        "error": str(exc),
                    }
                )

                if self.strict:
                    raise

        context.opportunities = calculated

        context.metadata["stake"] = {
            "input": len(opportunities),
            "calculated": len(calculated),
            "invalid": len(invalid),
            "bankroll_per_opportunity": (
                self.bankroll
            ),
            "details": invalid,
        }

        return context

    execute = process