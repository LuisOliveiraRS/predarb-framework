from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    allocate_quantities,
)


class ParallelStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.PARALLEL

    @staticmethod
    def _targets(value: Any) -> list[dict[str, Any]]:
        if value is None or isinstance(value, (str, bytes, Mapping)):
            if isinstance(value, str) and value.strip():
                value = [value]
            else:
                raise ValueError("PARALLEL exige uma coleção execution_targets.")

        targets: list[dict[str, Any]] = []
        for item in value:
            if isinstance(item, str):
                platform = item.strip()
                data: dict[str, Any] = {"platform": platform, "weight": 1.0}
            elif isinstance(item, Mapping):
                data = dict(item)
                platform = str(
                    data.get("platform", data.get("exchange", data.get("venue", "")))
                    or ""
                ).strip()
                data["platform"] = platform
            else:
                raise TypeError("Cada execution_target deve ser string ou Mapping.")
            if not platform:
                raise ValueError("Todo execution_target deve informar platform/exchange.")
            targets.append(data)
        if not targets:
            raise ValueError("execution_targets não pode ser vazio.")
        return targets

    def _build(self, context: ExecutionStrategyContext) -> None:
        targets = self._targets(
            context.options.get("targets", context.order.execution_targets)
        )
        total = context.order.remaining_quantity
        explicit = [target.get("quantity") for target in targets]

        if all(value is not None for value in explicit):
            quantities = [float(value) for value in explicit]
            if any(not isfinite(value) or value <= 0 for value in quantities):
                raise ValueError("As quantidades dos targets devem ser positivas.")
            if abs(sum(quantities) - total) > 1e-8:
                raise ValueError(
                    "A soma das quantidades dos targets deve ser igual à quantidade disponível."
                )
        elif any(value is not None for value in explicit):
            raise ValueError(
                "Informe quantity para todos os targets ou use apenas weight."
            )
        else:
            weights = [target.get("weight", 1.0) for target in targets]
            quantities = allocate_quantities(total, weights)

        for sequence, (target, quantity) in enumerate(
            zip(targets, quantities), start=1
        ):
            self._child(
                context,
                quantity=quantity,
                sequence=sequence,
                platform=target["platform"],
                market=str(target.get("market", context.order.market) or context.order.market),
                symbol=str(target.get("symbol", context.order.symbol) or context.order.symbol),
                price=target.get("price", context.order.price),
                metadata={
                    "parallel": True,
                    "target_weight": target.get("weight"),
                },
            )

        context.options["simultaneous"] = True
        context.metadata.update(
            targets=[target["platform"] for target in targets],
            simultaneous=True,
        )
        context.execution_reports.append(f"PARALLEL_PLAN_GENERATED:{len(targets)}")
