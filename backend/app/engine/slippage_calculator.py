from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.slippage_stage import SlippageStage


class SlippageCalculator:
    """
    Fachada de compatibilidade para o SlippageStage.

    O resultado oficial é uma estrutura contendo:

        rate
        percentage
        cost
        adjusted_profit
        adjusted_roi
        status

    O slippage não é mais representado apenas
    por um número sem unidade.
    """

    def __init__(
        self,
        *,
        require_liquidity: bool = False,
        max_slippage_rate: float | None = None,
        strict: bool = False,
    ) -> None:
        self.require_liquidity = bool(
            require_liquidity
        )

        self.max_slippage_rate = (
            max_slippage_rate
        )

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
        Sincroniza campos de modelos Opportunity.
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

        analysis = metadata.get("slippage")

        if not isinstance(analysis, Mapping):
            return

        if hasattr(opportunity, "slippage"):
            opportunity.slippage = dict(analysis)

        if hasattr(opportunity, "adjusted_profit"):
            opportunity.adjusted_profit = (
                analysis.get("adjusted_profit")
            )

        if hasattr(opportunity, "adjusted_roi"):
            opportunity.adjusted_roi = (
                analysis.get("adjusted_roi")
            )

    def calculate_one(
        self,
        opportunity: Any,
        *,
        require_liquidity: bool | None = None,
        max_slippage_rate: float | None = None,
        strict: bool | None = None,
    ) -> Any | None:
        results = self.calculate(
            [opportunity],
            require_liquidity=require_liquidity,
            max_slippage_rate=max_slippage_rate,
            strict=strict,
        )

        return results[0] if results else None

    def calculate(
        self,
        opportunities: Any,
        *,
        require_liquidity: bool | None = None,
        max_slippage_rate: float | None = None,
        strict: bool | None = None,
    ) -> list[Any]:
        resolved_require_liquidity = (
            self.require_liquidity
            if require_liquidity is None
            else bool(require_liquidity)
        )

        resolved_max_rate = (
            self.max_slippage_rate
            if max_slippage_rate is None
            else max_slippage_rate
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

        SlippageStage(
            require_liquidity=(
                resolved_require_liquidity
            ),
            max_slippage_rate=resolved_max_rate,
            strict=resolved_strict,
        ).process(context)

        results = list(
            context.opportunities or []
        )

        for opportunity in results:
            self._synchronize_model(opportunity)

        self.last_report = dict(
            context.metadata.get(
                "slippage",
                {},
            )
        )

        return results


slippage_calculator = SlippageCalculator()