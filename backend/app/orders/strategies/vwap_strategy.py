from __future__ import annotations

from datetime import datetime, timedelta, timezone
from math import isfinite
from typing import Any

from app.orders.execution_policy import ExecutionPolicy
from app.orders.execution_strategy import (
    ExecutionStrategy,
    ExecutionStrategyContext,
    allocate_quantities,
)


class VWAPStrategy(ExecutionStrategy):
    policy = ExecutionPolicy.VWAP

    DEFAULT_PROFILE = [0.05, 0.10, 0.15, 0.20, 0.20, 0.15, 0.10, 0.05]

    @staticmethod
    def _profile(value: Any) -> list[float]:
        if isinstance(value, (str, bytes)):
            raise TypeError("volume_profile deve ser uma coleção numérica.")
        try:
            profile = [float(weight) for weight in value]
        except (TypeError, ValueError) as exc:
            raise TypeError("volume_profile deve ser uma coleção numérica.") from exc
        if not profile:
            raise ValueError("volume_profile não pode ser vazio.")
        if any(not isfinite(weight) or weight <= 0 for weight in profile):
            raise ValueError("Todos os pesos do volume_profile devem ser positivos.")
        return profile

    def _build(self, context: ExecutionStrategyContext) -> None:
        profile = self._profile(
            context.options.get("volume_profile", self.DEFAULT_PROFILE)
        )
        interval = float(context.options.get("interval", 0.0))
        start_at = context.options.get("start_at") or datetime.now(timezone.utc)
        if interval < 0:
            raise ValueError("interval não pode ser negativo.")
        if not isinstance(start_at, datetime):
            raise TypeError("start_at deve ser datetime.")
        if start_at.tzinfo is None:
            start_at = start_at.replace(tzinfo=timezone.utc)

        quantities = allocate_quantities(context.order.remaining_quantity, profile)
        weight_sum = sum(profile)
        for index, (quantity, weight) in enumerate(
            zip(quantities, profile), start=1
        ):
            execute_at = start_at + timedelta(seconds=(index - 1) * interval)
            self._child(
                context,
                quantity=quantity,
                sequence=index,
                execute_at=execute_at,
                metadata={
                    "volume_weight": weight,
                    "normalized_weight": round(weight / weight_sum, 8),
                },
            )

        context.metadata.update(
            profile=list(profile),
            interval_seconds=interval,
            scheduled=True,
        )
        context.execution_reports.append(f"VWAP_PLAN_GENERATED:{len(profile)}")
