from __future__ import annotations

from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from math import isfinite
from typing import Any
from uuid import uuid4

from app.pipeline.pipeline_stage import PipelineStage


class OrderStage(PipelineStage):
    """
    Converte oportunidades aprovadas em intenções
    de ordem, sem enviar nada ao OMS ou às exchanges.

    A criação de objetos Order reais e o despacho
    serão consolidados durante a auditoria da
    camada Orders.
    """

    def __init__(
        self,
        *,
        require_approved: bool = True,
        strict: bool = False,
        order_type: str = "LIMIT",
        time_in_force: str = "GTC",
    ) -> None:
        self.require_approved = bool(
            require_approved
        )

        self.strict = bool(
            strict
        )

        self.order_type = self._text(
            order_type,
            "order_type",
        ).upper()

        self.time_in_force = self._text(
            time_in_force,
            "time_in_force",
        ).upper()

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(
            target,
            Mapping,
        ):
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
    ) -> str:
        if not isinstance(
            value,
            str,
        ):
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser uma string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"O campo {field_name!r} "
                "não pode ser vazio."
            )

        return normalized

    @staticmethod
    def _positive_number(
        value: Any,
        field_name: str,
    ) -> float:
        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if (
            not isfinite(number)
            or number <= 0
        ):
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser finito e maior "
                "que zero."
            )

        return number

    @classmethod
    def _stake_amount(
        cls,
        opportunity: Any,
        leg: str,
    ) -> float:
        stake = cls._read_field(
            opportunity,
            "stake",
            None,
        )

        amount = cls._read_field(
            stake,
            leg.lower(),
            None,
        )

        return cls._positive_number(
            amount,
            f"stake.{leg.lower()}",
        )

    @classmethod
    def _price(
        cls,
        opportunity: Any,
        leg: str,
    ) -> float:
        field_name = (
            f"{leg.lower()}_price"
        )

        price = cls._read_field(
            opportunity,
            field_name,
            None,
        )

        if price is None:
            prices = cls._read_field(
                opportunity,
                "prices",
                None,
            )

            price = cls._read_field(
                prices,
                leg.lower(),
                None,
            )

        number = cls._positive_number(
            price,
            field_name,
        )

        if number > 1:
            raise ValueError(
                f"O campo {field_name!r} "
                "deve estar entre 0 e 1."
            )

        return number

    @classmethod
    def _platform(
        cls,
        opportunity: Any,
        leg: str,
    ) -> str:
        field_name = (
            f"buy_{leg.lower()}_platform"
        )

        return cls._text(
            cls._read_field(
                opportunity,
                field_name,
                None,
            ),
            field_name,
        )

    @classmethod
    def _slippage_rate(
        cls,
        opportunity: Any,
    ) -> float:
        slippage = cls._read_field(
            opportunity,
            "slippage",
            None,
        )

        rate = cls._read_field(
            slippage,
            "rate",
            None,
        )

        if rate is None:
            rate = cls._read_field(
                opportunity,
                "slippage_rate",
                0.0,
            )

        try:
            number = float(
                rate
                or 0.0
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0.0

        if (
            not isfinite(number)
            or number < 0
        ):
            return 0.0

        return number

    def _build_leg(
        self,
        opportunity: Any,
        *,
        opportunity_index: int,
        leg: str,
    ) -> dict[str, Any]:
        question = self._text(
            self._read_field(
                opportunity,
                "question",
                None,
            ),
            "question",
        )

        platform = self._platform(
            opportunity,
            leg,
        )

        price = self._price(
            opportunity,
            leg,
        )

        notional = self._stake_amount(
            opportunity,
            leg,
        )

        quantity = (
            notional
            / price
        )

        slippage_rate = (
            self._slippage_rate(
                opportunity
            )
        )

        market_id = self._read_field(
            opportunity,
            "market_id",
            None,
        )

        symbol = str(
            market_id
            or question
        ).strip()

        return {
            "id": str(
                uuid4()
            ),
            "opportunity_index": (
                opportunity_index
            ),
            "leg": leg.upper(),
            "platform": platform,
            "symbol": symbol,
            "market": question,
            "side": "BUY",
            "order_type": (
                self.order_type
            ),
            "time_in_force": (
                self.time_in_force
            ),
            "price": round(
                price,
                6,
            ),
            "quantity": round(
                quantity,
                8,
            ),
            "notional": round(
                notional,
                2,
            ),
            "slippage_rate": round(
                slippage_rate,
                6,
            ),
            "max_price": round(
                min(
                    1.0,
                    price
                    * (
                        1.0
                        + slippage_rate
                    ),
                ),
                6,
            ),
            "status": "CREATED",
            "mode": "INTENT",
            "created_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

    def build_orders(
        self,
        opportunity: Any,
        *,
        opportunity_index: int,
    ) -> list[dict[str, Any]]:
        approved = bool(
            self._read_field(
                opportunity,
                "approved",
                False,
            )
        )

        if (
            self.require_approved
            and not approved
        ):
            raise ValueError(
                "A oportunidade não está "
                "aprovada para geração "
                "de ordens."
            )

        return [
            self._build_leg(
                opportunity,
                opportunity_index=(
                    opportunity_index
                ),
                leg="YES",
            ),
            self._build_leg(
                opportunity,
                opportunity_index=(
                    opportunity_index
                ),
                leg="NO",
            ),
        ]

    @staticmethod
    def _attach_orders(
        opportunity: Any,
        orders: list[
            dict[str, Any]
        ],
    ) -> Any:
        result = deepcopy(
            opportunity
        )

        if isinstance(
            result,
            dict,
        ):
            result["orders"] = orders

            return result

        metadata = getattr(
            result,
            "metadata",
            None,
        )

        if isinstance(
            metadata,
            dict,
        ):
            metadata["orders"] = deepcopy(
                orders
            )

        return result

    def process(
        self,
        context: Any,
    ) -> Any:
        opportunities = list(
            context.opportunities
            or []
        )

        enriched_opportunities: (
            list[Any]
        ) = []

        orders: list[
            dict[str, Any]
        ] = []

        rejected: list[
            dict[str, Any]
        ] = []

        for index, opportunity in enumerate(
            opportunities
        ):
            try:
                opportunity_orders = (
                    self.build_orders(
                        opportunity,
                        opportunity_index=index,
                    )
                )

                orders.extend(
                    opportunity_orders
                )

                enriched_opportunities.append(
                    self._attach_orders(
                        opportunity,
                        opportunity_orders,
                    )
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                rejected.append(
                    {
                        "index": index,
                        "error": str(exc),
                    }
                )

                if self.strict:
                    raise

        context.opportunities = (
            enriched_opportunities
        )

        context.orders = orders

        context.order = (
            orders[0]
            if orders
            else None
        )

        context.metadata["orders"] = {
            "input_opportunities": len(
                opportunities
            ),
            "accepted_opportunities": len(
                enriched_opportunities
            ),
            "rejected_opportunities": len(
                rejected
            ),
            "orders_created": len(
                orders
            ),
            "mode": "intent",
            "details": rejected,
        }

        return context

    execute = process