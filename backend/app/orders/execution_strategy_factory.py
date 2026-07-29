from __future__ import annotations

from typing import Any, Type

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import ExecutionStrategy, ExecutionStrategyPlan
from app.orders.order import Order
from app.orders.strategies.iceberg_strategy import IcebergStrategy
from app.orders.strategies.limit_strategy import LimitStrategy
from app.orders.strategies.market_strategy import MarketStrategy
from app.orders.strategies.parallel_strategy import ParallelStrategy
from app.orders.strategies.split_strategy import SplitStrategy
from app.orders.strategies.twap_strategy import TWAPStrategy
from app.orders.strategies.vwap_strategy import VWAPStrategy


class ExecutionStrategyFactory:
    """Registro determinístico das estratégias de planejamento do OMS.

    SMART e ADAPTIVE são estratégias contextuais: exigem ordem, venues e
    liquidez. Ambas geram planos e não autorizam execução real.
    """

    def __init__(self) -> None:
        self._registry: dict[ExecutionPolicy, Type[ExecutionStrategy]] = {
            ExecutionPolicy.MARKET: MarketStrategy,
            ExecutionPolicy.LIMIT: LimitStrategy,
            ExecutionPolicy.IOC: LimitStrategy,
            ExecutionPolicy.FOK: LimitStrategy,
            ExecutionPolicy.POST_ONLY: LimitStrategy,
            ExecutionPolicy.TWAP: TWAPStrategy,
            ExecutionPolicy.VWAP: VWAPStrategy,
            ExecutionPolicy.ICEBERG: IcebergStrategy,
            ExecutionPolicy.SPLIT: SplitStrategy,
            ExecutionPolicy.PARALLEL: ParallelStrategy,
        }

    def register(
        self,
        policy: ExecutionPolicy | str,
        strategy_class: Type[ExecutionStrategy],
        *,
        replace: bool = False,
    ) -> None:
        resolved = ExecutionPolicy.parse(policy)
        if not isinstance(strategy_class, type) or not issubclass(
            strategy_class,
            ExecutionStrategy,
        ):
            raise TypeError("strategy_class deve herdar de ExecutionStrategy.")
        if resolved in self._registry and not replace:
            raise ValueError(f"Já existe estratégia registrada para {resolved.value}.")
        self._registry[resolved] = strategy_class

    def build(self, policy: ExecutionPolicy | str) -> ExecutionStrategy:
        resolved = ExecutionPolicy.parse(policy)
        if resolved in {ExecutionPolicy.SMART, ExecutionPolicy.ADAPTIVE}:
            raise NotImplementedError(
                f"{resolved.value} exige order, venues e liquidez; use factory.plan(...)."
            )
        strategy_class = self._registry.get(resolved)
        if strategy_class is None:
            raise ValueError(f"Não existe estratégia para {resolved.value}.")
        return strategy_class(policy=resolved)

    create = build
    get = build

    def plan(
        self,
        order: Order,
        policy: ExecutionPolicy | str | None = None,
        **options: Any,
    ) -> ExecutionStrategyPlan:
        if not isinstance(order, Order):
            raise TypeError("order deve ser uma instância de Order.")
        resolved = ExecutionPolicy.parse(policy or order.execution_policy)

        if resolved in {ExecutionPolicy.SMART, ExecutionPolicy.ADAPTIVE}:
            from app.orders.smart_execution_engine import smart_execution_engine

            venues = options.pop("venues", None)
            result = smart_execution_engine.plan(
                order,
                venues,
                liquidity_levels=options.pop("liquidity_levels", None),
                require_full_liquidity=bool(
                    options.pop("require_full_liquidity", True)
                ),
                max_venues=options.pop("max_venues", None),
                adaptive=resolved is ExecutionPolicy.ADAPTIVE,
            )
            if options:
                unknown = ", ".join(sorted(options))
                raise TypeError(f"Opções {resolved.value} desconhecidas: {unknown}.")
            if not result.success or result.execution_plan is None:
                raise ValueError(
                    f"Planejamento {resolved.value} rejeitado: {result.reason}."
                )
            return result.execution_plan

        return self.build(resolved).plan(order, **options)

    def available(self) -> list[str]:
        return sorted(
            [policy.value for policy in self._registry]
            + [ExecutionPolicy.SMART.value, ExecutionPolicy.ADAPTIVE.value]
        )

    def status(self) -> dict[str, Any]:
        return {
            "available": self.available(),
            "contextual": [
                ExecutionPolicy.SMART.value,
                ExecutionPolicy.ADAPTIVE.value,
            ],
            "live_execution": False,
        }


execution_strategy_factory = ExecutionStrategyFactory()
