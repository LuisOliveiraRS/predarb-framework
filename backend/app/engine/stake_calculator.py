from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.engine.models import StakeResult
from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.stake_stage import StakeStage


class StakeCalculator:
    """
    Fachada de compatibilidade para o StakeStage.

    Calcula a distribuição da stake entre os lados
    Yes e No, utilizando a regra oficial do Pipeline.
    """

    def __init__(
        self,
        *,
        bankroll: float = 1_000.0,
        strict: bool = False,
    ) -> None:
        self.bankroll = float(bankroll)
        self.strict = bool(strict)

        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(
        opportunities: Any,
    ) -> list[Any]:
        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            Mapping,
        ):
            return [opportunities]

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "opportunities deve ser uma coleção."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(opportunities)

        return [opportunities]

    @staticmethod
    def _synchronize_model(
        opportunity: Any,
    ) -> None:
        """
        Sincroniza o resultado armazenado em metadata
        com modelos Opportunity que possuem StakeResult.
        """

        if isinstance(opportunity, Mapping):
            return

        metadata = getattr(
            opportunity,
            "metadata",
            None,
        )

        if not isinstance(metadata, dict):
            return

        stake_data = metadata.get("stake")

        if not isinstance(stake_data, Mapping):
            return

        if hasattr(opportunity, "stake"):
            opportunity.stake = StakeResult.from_value(
                stake_data
            )

    def calculate_one(
        self,
        opportunity: Any,
        *,
        bankroll: float | None = None,
        strict: bool | None = None,
    ) -> Any | None:
        results = self.calculate(
            [opportunity],
            bankroll=bankroll,
            strict=strict,
        )

        return results[0] if results else None

    def calculate(
        self,
        opportunities: Any,
        bankroll: float | None = None,
        *,
        strict: bool | None = None,
    ) -> list[Any]:
        """
        Calcula a stake de uma coleção.

        Preserva a assinatura legada:

            calculate(opportunities, bankroll=1000)
        """

        resolved_bankroll = (
            self.bankroll
            if bankroll is None
            else float(bankroll)
        )

        resolved_strict = (
            self.strict
            if strict is None
            else bool(strict)
        )

        context = PipelineContext(
            {
                "opportunities": self._as_list(
                    opportunities
                ),
            }
        )

        StakeStage(
            bankroll=resolved_bankroll,
            strict=resolved_strict,
        ).process(context)

        results = list(
            context.opportunities or []
        )

        for opportunity in results:
            self._synchronize_model(opportunity)

        self.last_report = dict(
            context.metadata.get(
                "stake",
                {},
            )
        )

        return results


stake_calculator = StakeCalculator()