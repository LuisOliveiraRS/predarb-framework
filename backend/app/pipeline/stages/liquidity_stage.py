from __future__ import annotations

from collections.abc import Mapping
from copy import copy
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class LiquidityStage(PipelineStage):
    """
    Analisa a liquidez das oportunidades.

    Classificação preservada:

        HIGH   >= 10.000
        MEDIUM >= 3.000
        LOW    <  3.000

    Quando nenhum dado de liquidez estiver disponível,
    o nível será UNKNOWN.
    """

    HIGH_THRESHOLD = 10_000.0
    MEDIUM_THRESHOLD = 3_000.0

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
    ) -> float | None:
        if value is None or isinstance(
            value,
            bool,
        ):
            return None

        try:
            number = float(
                value,
            )

        except (TypeError, ValueError):
            return None

        if not isfinite(number) or number < 0:
            return None

        return number

    @staticmethod
    def _clone(
        opportunity: Any,
    ) -> Any:
        if isinstance(opportunity, Mapping):
            return dict(
                opportunity,
            )

        return copy(
            opportunity,
        )

    @staticmethod
    def _set_analysis(
        target: Any,
        analysis: dict[str, Any],
    ) -> None:
        if isinstance(target, dict):
            target["liquidity"] = analysis
            target["liquidity_value"] = (
                analysis["available"]
            )
            return

        if hasattr(target, "liquidity"):
            setattr(
                target,
                "liquidity",
                analysis,
            )
            return

        metadata = getattr(
            target,
            "metadata",
            None,
        )

        if isinstance(metadata, dict):
            metadata["liquidity"] = analysis

    @classmethod
    def _market_liquidity(
        cls,
        market: Any,
    ) -> float | None:
        """
        Recupera liquidez ou volume de um mercado.
        """

        if market is None:
            return None

        liquidity = cls._number(
            cls._read_field(
                market,
                "liquidity",
                None,
            )
        )

        if liquidity is not None:
            return liquidity

        return cls._number(
            cls._read_field(
                market,
                "volume",
                None,
            )
        )

    @classmethod
    def _direct_liquidity(
        cls,
        opportunity: Any,
    ) -> float | None:
        direct = cls._read_field(
            opportunity,
            "liquidity",
            None,
        )

        if isinstance(direct, Mapping):
            direct = direct.get(
                "available",
            )

        direct_number = cls._number(
            direct,
        )

        if direct_number is not None:
            return direct_number

        return cls._number(
            cls._read_field(
                opportunity,
                "liquidity_value",
                None,
            )
        )

    @classmethod
    def _resolve_liquidity(
        cls,
        opportunity: Any,
    ) -> tuple[float | None, str]:
        """
        Recupera a liquidez efetiva e sua origem.
        """

        direct = cls._direct_liquidity(
            opportunity,
        )

        if direct is not None:
            return (
                direct,
                "opportunity",
            )

        volume_yes = cls._number(
            cls._read_field(
                opportunity,
                "volume_yes",
                None,
            )
        )

        volume_no = cls._number(
            cls._read_field(
                opportunity,
                "volume_no",
                None,
            )
        )

        if (
            volume_yes is not None
            and volume_no is not None
        ):
            return (
                min(
                    volume_yes,
                    volume_no,
                ),
                "side_volumes",
            )

        market_yes = cls._read_field(
            opportunity,
            "market_yes",
            None,
        )

        market_no = cls._read_field(
            opportunity,
            "market_no",
            None,
        )

        yes_liquidity = cls._market_liquidity(
            market_yes,
        )

        no_liquidity = cls._market_liquidity(
            market_no,
        )

        available = [
            value
            for value in (
                yes_liquidity,
                no_liquidity,
            )
            if value is not None
        ]

        if available:
            return (
                min(
                    available,
                ),
                "markets",
            )

        return (
            None,
            "unavailable",
        )

    @classmethod
    def _level(
        cls,
        available: float | None,
    ) -> str:
        if available is None:
            return "UNKNOWN"

        if available >= cls.HIGH_THRESHOLD:
            return "HIGH"

        if available >= cls.MEDIUM_THRESHOLD:
            return "MEDIUM"

        return "LOW"

    def analyze_opportunity(
        self,
        opportunity: Any,
    ) -> Any:
        result = self._clone(
            opportunity,
        )

        available, source = (
            self._resolve_liquidity(
                opportunity,
            )
        )

        analysis = {
            "available": (
                round(
                    available,
                    2,
                )
                if available is not None
                else None
            ),
            "level": self._level(
                available,
            ),
            "known": (
                available is not None
            ),
            "source": source,
        }

        self._set_analysis(
            result,
            analysis,
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

        analyzed = [
            self.analyze_opportunity(
                opportunity,
            )
            for opportunity in opportunities
        ]

        context.opportunities = analyzed

        known = sum(
            1
            for opportunity in analyzed
            if self._resolve_liquidity(
                opportunity,
            )[0]
            is not None
        )

        context.metadata["liquidity"] = {
            "analyzed": len(analyzed),
            "known": known,
            "unknown": (
                len(analyzed) - known
            ),
        }

        return context