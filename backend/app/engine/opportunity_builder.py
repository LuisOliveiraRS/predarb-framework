from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.engine.arbitrage_calculator import (
    ArbitrageCalculator,
    calculator,
)


class OpportunityBuilder:
    """
    Transforma dois mercados compatíveis em uma
    oportunidade canônica.

    O builder aceita objetos Market e dicionários.
    """

    def __init__(
        self,
        *,
        arbitrage_calculator: (
            ArbitrageCalculator
            | None
        ) = None,
    ) -> None:
        self.calculator = (
            arbitrage_calculator
            or calculator
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
    def _text(
        value: Any,
        field_name: str,
        *,
        default: str | None = None,
    ) -> str:
        if value is None:
            if default is not None:
                return default

            raise ValueError(
                f"O campo {field_name!r} "
                "é obrigatório."
            )

        normalized = str(value).strip()

        if not normalized:
            if default is not None:
                return default

            raise ValueError(
                f"O campo {field_name!r} "
                "não pode ser vazio."
            )

        return normalized

    @staticmethod
    def _number(
        value: Any,
        *,
        default: float = 0.0,
    ) -> float:
        if value is None or isinstance(
            value,
            bool,
        ):
            return float(default)

        try:
            number = float(value)

        except (TypeError, ValueError):
            return float(default)

        if not isfinite(number):
            return float(default)

        return number

    @classmethod
    def _datetime_value(
        cls,
        value: Any,
    ) -> str | None:
        if value is None:
            return None

        if isinstance(value, datetime):
            if value.tzinfo is None:
                value = value.replace(
                    tzinfo=timezone.utc,
                )

            return value.isoformat()

        normalized = str(value).strip()

        return normalized or None

    @classmethod
    def _available_volume(
        cls,
        market: Any,
    ) -> float:
        """
        Prioriza volume e usa liquidity
        como alternativa.
        """

        volume = cls._number(
            cls._read_field(
                market,
                "volume",
                None,
            )
        )

        if volume > 0:
            return volume

        return max(
            0.0,
            cls._number(
                cls._read_field(
                    market,
                    "liquidity",
                    0.0,
                )
            ),
        )

    @classmethod
    def _market_snapshot(
        cls,
        market: Any,
    ) -> dict[str, Any]:
        """
        Converte um Market ou dicionário em uma
        estrutura segura para serialização.
        """

        metadata = cls._read_field(
            market,
            "metadata",
            {},
        )

        if not isinstance(metadata, Mapping):
            metadata = {}

        return {
            "platform": cls._text(
                cls._read_field(
                    market,
                    "platform",
                    None,
                ),
                "platform",
            ),
            "question": cls._text(
                cls._read_field(
                    market,
                    "question",
                    None,
                ),
                "question",
            ),
            "yes": round(
                cls._number(
                    cls._read_field(
                        market,
                        "yes",
                        0.0,
                    )
                ),
                6,
            ),
            "no": round(
                cls._number(
                    cls._read_field(
                        market,
                        "no",
                        0.0,
                    )
                ),
                6,
            ),
            "connector": cls._text(
                cls._read_field(
                    market,
                    "connector",
                    "unknown",
                ),
                "connector",
                default="unknown",
            ),
            "liquidity": round(
                max(
                    0.0,
                    cls._number(
                        cls._read_field(
                            market,
                            "liquidity",
                            0.0,
                        )
                    ),
                ),
                2,
            ),
            "volume": round(
                max(
                    0.0,
                    cls._number(
                        cls._read_field(
                            market,
                            "volume",
                            0.0,
                        )
                    ),
                ),
                2,
            ),
            "fee": round(
                max(
                    0.0,
                    cls._number(
                        cls._read_field(
                            market,
                            "fee",
                            0.0,
                        )
                    ),
                ),
                6,
            ),
            "market_id": cls._text(
                cls._read_field(
                    market,
                    "market_id",
                    "",
                ),
                "market_id",
                default="",
            ),
            "category": cls._text(
                cls._read_field(
                    market,
                    "category",
                    "",
                ),
                "category",
                default="",
            ),
            "asset": cls._text(
                cls._read_field(
                    market,
                    "asset",
                    "",
                ),
                "asset",
                default="",
            ),
            "event_type": cls._text(
                cls._read_field(
                    market,
                    "event_type",
                    "",
                ),
                "event_type",
                default="",
            ),
            "status": cls._text(
                cls._read_field(
                    market,
                    "status",
                    "open",
                ),
                "status",
                default="open",
            ),
            "created_at": cls._datetime_value(
                cls._read_field(
                    market,
                    "created_at",
                    None,
                )
            ),
            "expires_at": cls._datetime_value(
                cls._read_field(
                    market,
                    "expires_at",
                    None,
                )
            ),
            "metadata": dict(metadata),
        }

    @staticmethod
    def _confidence(
        similarity: Any,
    ) -> tuple[float, float]:
        """
        Retorna:

        - similaridade em escala de 0 a 1;
        - confiança em escala de 0 a 100.
        """

        try:
            score = float(similarity)

        except (TypeError, ValueError):
            score = 0.0

        if not isfinite(score):
            score = 0.0

        if score > 1:
            score = score / 100

        score = min(
            1.0,
            max(
                0.0,
                score,
            ),
        )

        return (
            round(
                score,
                6,
            ),
            round(
                score * 100,
                2,
            ),
        )

    def build(
        self,
        market_yes: Any,
        market_no: Any,
        *,
        similarity: Any = 1.0,
    ) -> dict[str, Any] | None:
        """
        Constrói uma oportunidade comprando:

        - Yes em market_yes;
        - No em market_no.
        """

        yes_snapshot = self._market_snapshot(
            market_yes
        )

        no_snapshot = self._market_snapshot(
            market_no
        )

        if (
            yes_snapshot["platform"].casefold()
            == no_snapshot["platform"].casefold()
        ):
            return None

        result = self.calculator.calculate(
            yes_snapshot["yes"],
            no_snapshot["no"],
        )

        if result is None:
            return None

        similarity_score, confidence = (
            self._confidence(
                similarity
            )
        )

        yes_id = (
            yes_snapshot["market_id"]
            or yes_snapshot["platform"]
        )

        no_id = (
            no_snapshot["market_id"]
            or no_snapshot["platform"]
        )

        opportunity_id = (
            f"{yes_id}:YES|{no_id}:NO"
        )

        volume_yes = self._available_volume(
            market_yes
        )

        volume_no = self._available_volume(
            market_no
        )

        return {
            **result,
            "opportunity_id": opportunity_id,
            "market_id": opportunity_id,
            "question": yes_snapshot["question"],
            "matched_question": (
                no_snapshot["question"]
            ),
            "buy_yes_platform": (
                yes_snapshot["platform"]
            ),
            "buy_no_platform": (
                no_snapshot["platform"]
            ),
            "platforms": [
                yes_snapshot["platform"],
                no_snapshot["platform"],
            ],
            "connector_yes": (
                yes_snapshot["connector"]
            ),
            "connector_no": (
                no_snapshot["connector"]
            ),
            "similarity": similarity_score,
            "confidence": confidence,
            "match_score": confidence,
            "volume_yes": round(
                volume_yes,
                2,
            ),
            "volume_no": round(
                volume_no,
                2,
            ),
            "liquidity_yes": round(
                max(
                    0.0,
                    yes_snapshot["liquidity"],
                ),
                2,
            ),
            "liquidity_no": round(
                max(
                    0.0,
                    no_snapshot["liquidity"],
                ),
                2,
            ),
            "market_yes": yes_snapshot,
            "market_no": no_snapshot,
            "score": 0.0,
            "approved": False,
            "created_at": datetime.now(
                timezone.utc,
            ).isoformat(),
            "metadata": {
                "source": (
                    "cross_platform_comparator"
                ),
                "yes_market_id": (
                    yes_snapshot["market_id"]
                ),
                "no_market_id": (
                    no_snapshot["market_id"]
                ),
                "yes_fee": yes_snapshot["fee"],
                "no_fee": no_snapshot["fee"],
                "fees_applied": False,
            },
        }


opportunity_builder = OpportunityBuilder()