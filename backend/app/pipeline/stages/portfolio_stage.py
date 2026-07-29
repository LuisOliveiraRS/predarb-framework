from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class PortfolioStage(PipelineStage):
    """
    Simula a alocação do portfólio sem reservar
    capital e sem criar posições.

    A reserva real deve ocorrer somente na camada
    de execução, depois da confirmação das ordens.
    """

    def __init__(
        self,
        *,
        total_bankroll: float = 10_000.0,
        max_position_size: float = 0.10,
        max_total_exposure: float = 0.50,
    ) -> None:
        self.total_bankroll = (
            self._positive_number(
                total_bankroll,
                "total_bankroll",
            )
        )

        self.max_position_size = (
            self._ratio(
                max_position_size,
                "max_position_size",
            )
        )

        self.max_total_exposure = (
            self._ratio(
                max_total_exposure,
                "max_total_exposure",
            )
        )

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
    def _ratio(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        number = cls._number(
            value,
            field_name,
        )

        if not 0 < number <= 1:
            raise ValueError(
                f"O campo {field_name!r} "
                "deve estar entre 0 e 1."
            )

        return number

    @classmethod
    def _stake_total(
        cls,
        opportunity: Any,
    ) -> float:
        stake = cls._read_field(
            opportunity,
            "stake",
            None,
        )

        total = cls._read_field(
            stake,
            "total",
            None,
        )

        if total is None:
            total = cls._read_field(
                stake,
                "amount",
                None,
            )

        if total is None:
            yes_stake = cls._read_field(
                stake,
                "yes",
                None,
            )

            no_stake = cls._read_field(
                stake,
                "no",
                None,
            )

            if (
                yes_stake is not None
                and no_stake is not None
            ):
                total = (
                    cls._number(
                        yes_stake,
                        "stake.yes",
                    )
                    + cls._number(
                        no_stake,
                        "stake.no",
                    )
                )

        return cls._positive_number(
            total,
            "stake.total",
        )

    @staticmethod
    def _set_portfolio(
        opportunity: Any,
        analysis: dict[str, Any],
    ) -> None:
        if isinstance(opportunity, dict):
            opportunity["portfolio"] = analysis
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["portfolio"] = analysis

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or [],
        )

        approved: list[Any] = []
        rejected: list[dict[str, Any]] = []

        available = self.total_bankroll
        allocated = 0.0

        max_position_amount = (
            self.total_bankroll
            * self.max_position_size
        )

        max_exposure_amount = (
            self.total_bankroll
            * self.max_total_exposure
        )

        for index, opportunity in enumerate(
            opportunities,
        ):
            result = deepcopy(
                opportunity,
            )

            reasons: list[str] = []

            try:
                stake_total = (
                    self._stake_total(
                        opportunity,
                    )
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                stake_total = 0.0

                reasons.append(
                    str(exc),
                )

            if stake_total > max_position_amount:
                reasons.append(
                    "A stake excede o limite "
                    "por posição."
                )

            if (
                allocated + stake_total
                > max_exposure_amount
            ):
                reasons.append(
                    "A alocação excede a exposição "
                    "total permitida."
                )

            if stake_total > available:
                reasons.append(
                    "Bankroll disponível insuficiente."
                )

            if reasons:
                analysis = {
                    "approved": False,
                    "stake": round(
                        stake_total,
                        2,
                    ),
                    "reasons": reasons,
                }

                self._set_portfolio(
                    result,
                    analysis,
                )

                rejected.append(
                    {
                        "index": index,
                        "reasons": reasons,
                    }
                )

                continue

            allocated += stake_total
            available -= stake_total

            analysis = {
                "approved": True,
                "stake": round(
                    stake_total,
                    2,
                ),
                "available_after": round(
                    available,
                    2,
                ),
                "allocated_total": round(
                    allocated,
                    2,
                ),
                "utilization": round(
                    allocated
                    / self.total_bankroll,
                    4,
                ),
            }

            self._set_portfolio(
                result,
                analysis,
            )

            approved.append(
                result,
            )

        context.opportunities = approved

        context.metadata["portfolio"] = {
            "input": len(opportunities),
            "approved": len(approved),
            "rejected": len(rejected),
            "total_bankroll": (
                self.total_bankroll
            ),
            "available": round(
                available,
                2,
            ),
            "allocated": round(
                allocated,
                2,
            ),
            "max_position_amount": round(
                max_position_amount,
                2,
            ),
            "max_exposure_amount": round(
                max_exposure_amount,
                2,
            ),
            "details": rejected,
            "reservation_mode": "simulation",
        }

        return context

    execute = process