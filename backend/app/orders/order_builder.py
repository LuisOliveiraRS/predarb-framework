from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.orders.order import Order
from app.orders.order_batch import OrderBatch
from app.orders.order_side import OrderSide
from app.orders.order_type import OrderType
from app.orders.order_validator import OrderValidator, order_validator
from app.orders.time_in_force import TimeInForce


class OrderBuilder:
    """
    Constrói ordens individuais, intenções e lotes de arbitragem.

    Contratos preservados:

        order_builder.build(opportunity)
        order_builder.build(platform=..., market=..., ...)

    Integrações oficiais adicionadas:

        order_builder.build_from_execution_plan(plan)
        order_builder.build_pair_from_execution_plan(plan)
    """

    EXECUTION_PLAN_FIELDS = (
        "question",
        "yes_platform",
        "no_platform",
        "yes_price",
        "no_price",
        "yes_stake",
        "no_stake",
    )

    def __init__(
        self,
        *,
        validator: OrderValidator | None = None,
        validate_orders: bool = True,
    ) -> None:
        self.validator = validator or order_validator
        self.validate_orders = bool(validate_orders)

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @staticmethod
    def _positive_number(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"O campo {field_name!r} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"O campo {field_name!r} deve ser numérico.") from exc
        if not isfinite(number) or number <= 0:
            raise ValueError(
                f"O campo {field_name!r} deve ser finito e maior que zero."
            )
        return number

    @classmethod
    def is_execution_plan(cls, value: Any) -> bool:
        """Reconhece ``ExecutionPlan`` sem criar dependência circular.

        O reconhecimento é estrutural e também aceita o resultado de
        ``ExecutionPlan.to_dict()``.
        """

        if value is None:
            return False
        return all(cls._read(value, field_name, None) is not None for field_name in cls.EXECUTION_PLAN_FIELDS)

    @classmethod
    def _price(cls, opportunity: Any, leg: str) -> float:
        field_name = f"{leg.lower()}_price"
        value = cls._read(opportunity, field_name, None)
        if value is None:
            prices = cls._read(opportunity, "prices", {})
            value = cls._read(prices, leg.lower(), None)
        price = cls._positive_number(value, field_name)
        if price > 1:
            raise ValueError(f"O campo {field_name!r} deve estar entre 0 e 1.")
        return price

    @classmethod
    def _stake(cls, opportunity: Any, leg: str) -> float:
        stake = cls._read(opportunity, "stake", None)
        value = cls._read(stake, leg.lower(), None)
        return cls._positive_number(value, f"stake.{leg.lower()}")

    @classmethod
    def _platform(cls, opportunity: Any, leg: str) -> str:
        field_name = f"buy_{leg.lower()}_platform"
        platform = str(cls._read(opportunity, field_name, "") or "").strip()
        if not platform:
            raise ValueError(f"O campo {field_name!r} é obrigatório.")
        return platform

    @classmethod
    def _question(cls, opportunity: Any) -> str:
        question = str(cls._read(opportunity, "question", "") or "").strip()
        if not question:
            raise ValueError("O campo 'question' é obrigatório.")
        return question

    @classmethod
    def _opportunity_id(cls, source: Any) -> str:
        metadata = cls._read(source, "metadata", {})
        opportunity = cls._read(source, "opportunity", None)

        candidates = (
            cls._read(metadata, "opportunity_id", ""),
            cls._read(source, "opportunity_id", ""),
            cls._read(opportunity, "opportunity_id", ""),
            cls._read(opportunity, "market_id", ""),
        )

        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if normalized:
                return normalized
        return ""

    @classmethod
    def _execution_plan_symbol(cls, plan: Any, leg: str, question: str) -> str:
        metadata = cls._read(plan, "metadata", {})
        opportunity = cls._read(plan, "opportunity", None)
        lower_leg = leg.lower()

        market_snapshot = cls._read(opportunity, f"market_{lower_leg}", {})
        candidates = (
            cls._read(metadata, f"{lower_leg}_symbol", ""),
            cls._read(metadata, f"{lower_leg}_market_id", ""),
            cls._read(market_snapshot, "symbol", ""),
            cls._read(market_snapshot, "market_id", ""),
            cls._read(opportunity, f"{lower_leg}_symbol", ""),
            cls._read(opportunity, f"{lower_leg}_market_id", ""),
            cls._read(opportunity, "market_id", ""),
            question,
        )

        for candidate in candidates:
            normalized = str(candidate or "").strip()
            if normalized:
                return normalized
        return question

    @classmethod
    def _execution_plan_snapshot(cls, plan: Any) -> dict[str, Any]:
        to_dict = getattr(plan, "to_dict", None)
        if callable(to_dict):
            snapshot = to_dict()
            if isinstance(snapshot, Mapping):
                return dict(snapshot)

        return {
            field_name: cls._read(plan, field_name, None)
            for field_name in (
                *cls.EXECUTION_PLAN_FIELDS,
                "total_stake",
                "total_price",
                "expected_profit",
                "estimated_profit",
                "estimated_roi",
                "max_latency",
                "simultaneous",
                "retry",
                "cancel_on_failure",
                "execute",
                "approved",
                "reason",
                "created_at",
                "metadata",
            )
        }

    @classmethod
    def _execution_plan_approved(cls, plan: Any) -> bool:
        execute = cls._read(plan, "execute", None)
        approved = cls._read(plan, "approved", None)
        if execute is not None:
            return bool(execute)
        return bool(approved)

    @classmethod
    def execution_plan_approved(cls, plan: Any) -> bool:
        return cls._execution_plan_approved(plan)

    def _finalize(self, order: Order, *, validate: bool | None = None) -> Order:
        resolved_validate = self.validate_orders if validate is None else bool(validate)
        if resolved_validate:
            self.validator.validate_or_raise(order)
        return order

    def build_order(
        self,
        *,
        platform: str,
        market: str | None = None,
        symbol: str | None = None,
        side: OrderSide | str,
        quantity: Any,
        order_type: OrderType | str = OrderType.MARKET,
        price: Any = 0.0,
        time_in_force: TimeInForce | str = TimeInForce.GTC,
        validate: bool | None = None,
        **kwargs: Any,
    ) -> Order:
        order = Order(
            symbol=symbol or market,
            platform=platform,
            market=market or symbol,
            side=side,
            quantity=quantity,
            order_type=order_type,
            price=price,
            time_in_force=time_in_force,
            **kwargs,
        )
        return self._finalize(order, validate=validate)

    def build_from_intent(
        self,
        intent: Mapping[str, Any],
        *,
        validate: bool | None = None,
    ) -> Order:
        if not isinstance(intent, Mapping):
            raise TypeError("intent deve ser um Mapping.")

        metadata = dict(intent.get("metadata", {}) or {})
        for key in (
            "opportunity_index",
            "notional",
            "slippage_rate",
            "max_price",
        ):
            if key in intent:
                metadata[key] = intent[key]

        return self.build_order(
            platform=str(intent.get("platform", "") or ""),
            market=str(intent.get("market", intent.get("symbol", "")) or ""),
            symbol=str(intent.get("symbol", intent.get("market", "")) or ""),
            side=intent.get("side", OrderSide.BUY),
            quantity=intent.get("quantity"),
            order_type=intent.get("order_type", OrderType.LIMIT),
            price=intent.get("price", 0.0),
            time_in_force=intent.get("time_in_force", TimeInForce.GTC),
            order_id=intent.get("id"),
            status=intent.get("status", "CREATED"),
            created_at=intent.get("created_at"),
            opportunity_id=str(intent.get("opportunity_id", "") or ""),
            leg=str(intent.get("leg", "") or ""),
            mode=str(intent.get("mode", "INTENT") or "INTENT"),
            metadata=metadata,
            validate=validate,
        )

    def _build_leg(
        self,
        opportunity: Any,
        leg: str,
        *,
        validate: bool | None = None,
    ) -> Order:
        question = self._question(opportunity)
        platform = self._platform(opportunity, leg)
        price = self._price(opportunity, leg)
        stake = self._stake(opportunity, leg)
        quantity = stake / price

        opportunity_id = str(
            self._read(
                opportunity,
                "opportunity_id",
                self._read(opportunity, "market_id", ""),
            )
            or ""
        ).strip()

        market_snapshot = self._read(
            opportunity,
            f"market_{leg.lower()}",
            {},
        )
        symbol = str(
            self._read(market_snapshot, "market_id", "")
            or self._read(opportunity, "market_id", "")
            or question
        ).strip()

        return self.build_order(
            platform=platform,
            market=question,
            symbol=symbol,
            side=OrderSide.BUY,
            quantity=round(quantity, 8),
            order_type=OrderType.LIMIT,
            price=price,
            time_in_force=TimeInForce.GTC,
            opportunity_id=opportunity_id,
            leg=leg,
            mode="ARBITRAGE",
            metadata={
                "stake_notional": round(stake, 2),
                "source": "order_builder",
            },
            validate=validate,
        )

    def build_pair(
        self,
        opportunity: Any,
        *,
        validate: bool | None = None,
    ) -> dict[str, Order]:
        return {
            "yes": self._build_leg(opportunity, "YES", validate=validate),
            "no": self._build_leg(opportunity, "NO", validate=validate),
        }

    def build_pair_from_execution_plan(
        self,
        plan: Any,
        *,
        validate: bool | None = None,
        require_approved: bool = True,
    ) -> dict[str, Order]:
        """Converte um plano aprovado da camada ``app.execution`` em ordens.

        O método não registra, não submete e não envia as ordens. As duas
        pernas são criadas em ``CREATED`` e permanecem sob controle do OMS.
        """

        if not self.is_execution_plan(plan):
            raise TypeError(
                "plan deve ser um ExecutionPlan ou Mapping compatível."
            )

        approved = self._execution_plan_approved(plan)
        if require_approved and not approved:
            reason = str(self._read(plan, "reason", "PLAN_NOT_APPROVED") or "PLAN_NOT_APPROVED")
            raise ValueError(f"O ExecutionPlan não está aprovado: {reason}.")

        question = str(self._read(plan, "question", "") or "").strip()
        if not question:
            raise ValueError("O ExecutionPlan deve possuir question.")

        opportunity_id = self._opportunity_id(plan)
        snapshot = self._execution_plan_snapshot(plan)
        created_at = self._read(plan, "created_at", None)
        if isinstance(created_at, datetime):
            normalized_created_at = (
                created_at
                if created_at.tzinfo is not None
                else created_at.replace(tzinfo=timezone.utc)
            ).isoformat()
        else:
            normalized_created_at = str(created_at or "").strip()

        common_metadata = {
            "source": "execution_plan",
            "execution_plan": snapshot,
            "execution_plan_approved": approved,
            "expected_profit": self._read(plan, "expected_profit", 0.0),
            "estimated_roi": self._read(plan, "estimated_roi", 0.0),
            "max_latency": self._read(plan, "max_latency", 0.0),
            "retry": self._read(plan, "retry", 0),
            "simultaneous": bool(self._read(plan, "simultaneous", True)),
            "cancel_on_failure": bool(
                self._read(plan, "cancel_on_failure", True)
            ),
            "execution_plan_created_at": normalized_created_at,
        }

        orders: dict[str, Order] = {}
        for leg in ("YES", "NO"):
            lower_leg = leg.lower()
            platform = str(
                self._read(plan, f"{lower_leg}_platform", "") or ""
            ).strip()
            if not platform:
                raise ValueError(
                    f"O ExecutionPlan deve possuir {lower_leg}_platform."
                )

            price = self._positive_number(
                self._read(plan, f"{lower_leg}_price", None),
                f"{lower_leg}_price",
            )
            if price > 1:
                raise ValueError(
                    f"O campo {lower_leg}_price deve estar entre 0 e 1."
                )

            stake = self._positive_number(
                self._read(plan, f"{lower_leg}_stake", None),
                f"{lower_leg}_stake",
            )
            quantity = round(stake / price, 8)
            symbol = self._execution_plan_symbol(plan, leg, question)

            orders[lower_leg] = self.build_order(
                platform=platform,
                market=question,
                symbol=symbol,
                side=OrderSide.BUY,
                quantity=quantity,
                order_type=OrderType.LIMIT,
                price=price,
                time_in_force=TimeInForce.GTC,
                opportunity_id=opportunity_id,
                leg=leg,
                mode="EXECUTION_PLAN",
                execution_policy="LIMIT",
                metadata={
                    **common_metadata,
                    "stake_notional": round(stake, 2),
                    "plan_leg": leg,
                },
                validate=validate,
            )

        return orders

    def build_from_execution_plan(
        self,
        plan: Any,
        *,
        validate: bool | None = None,
        require_approved: bool = True,
    ) -> OrderBatch:
        pair = self.build_pair_from_execution_plan(
            plan,
            validate=validate,
            require_approved=require_approved,
        )

        return OrderBatch(
            pair,
            opportunity_id=self._opportunity_id(plan),
            simultaneous=bool(self._read(plan, "simultaneous", True)),
            cancel_on_failure=bool(
                self._read(plan, "cancel_on_failure", True)
            ),
            metadata={
                "source": "execution_plan",
                "execution_plan": self._execution_plan_snapshot(plan),
                "live_execution": False,
            },
        )

    build_execution_batch = build_from_execution_plan

    def build_orders(
        self,
        opportunity: Any,
        *,
        validate: bool | None = None,
    ) -> list[Order]:
        pair = self.build_pair(opportunity, validate=validate)
        return [pair["yes"], pair["no"]]

    def build(
        self,
        opportunity: Any = None,
        *,
        validate: bool | None = None,
        **kwargs: Any,
    ) -> Order | dict[str, Order] | OrderBatch:
        if opportunity is None:
            return self.build_order(validate=validate, **kwargs)

        if kwargs:
            if isinstance(opportunity, Mapping):
                merged = dict(opportunity)
                merged.update(kwargs)
                opportunity = merged
            else:
                raise TypeError(
                    "Não combine um objeto opportunity com kwargs de ordem."
                )

        if self.is_execution_plan(opportunity):
            return self.build_from_execution_plan(
                opportunity,
                validate=validate,
            )

        if isinstance(opportunity, Mapping):
            is_arbitrage = (
                "buy_yes_platform" in opportunity
                or "buy_no_platform" in opportunity
                or "stake" in opportunity
            )
            if is_arbitrage:
                return self.build_pair(opportunity, validate=validate)
            return self.build_from_intent(opportunity, validate=validate)

        if hasattr(opportunity, "buy_yes_platform") or hasattr(opportunity, "stake"):
            return self.build_pair(opportunity, validate=validate)

        raise TypeError(
            "opportunity deve ser uma oportunidade, ExecutionPlan ou Mapping de ordem."
        )


order_builder = OrderBuilder()
