from __future__ import annotations

from typing import Any, Callable, Mapping

from app.core.settings import settings
from app.execution.testnet_guard import (
    HyperliquidTestnetGuard,
    TestnetExecutionPolicy,
    hyperliquid_testnet_guard,
)
from app.exchanges.exchange_factory import exchange_factory


class ExchangeManager:
    """Camada central protegida de comunicação com exchanges."""

    def __init__(
        self,
        *,
        registry: Any | None = None,
        guard: HyperliquidTestnetGuard | None = None,
        policy_provider: Callable[
            [], TestnetExecutionPolicy
        ] | None = None,
    ) -> None:
        self.registry = (
            registry
            if registry is not None
            else exchange_factory.build()
        )
        self.guard = guard or hyperliquid_testnet_guard
        self._policy_provider = (
            policy_provider or self._settings_policy
        )

    @staticmethod
    def _settings_policy() -> TestnetExecutionPolicy:
        return TestnetExecutionPolicy(
            enabled=(
                settings
                .HYPERLIQUID_TESTNET_EXECUTION_ENABLED
            ),
            execution_authorized=(
                settings
                .HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED
            ),
            max_order_notional=(
                settings
                .HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL
            ),
            api_url=settings.HYPERLIQUID_TESTNET_API_URL,
        )

    @staticmethod
    def _platform(order: Any) -> str:
        if isinstance(order, Mapping):
            value = order.get("platform", "")
        else:
            value = getattr(order, "platform", "")

        platform = str(value or "").strip().lower()

        if not platform:
            raise ValueError(
                "A ordem deve informar uma plataforma."
            )

        return platform

    def adapter(self, exchange: str):
        return self.registry.get(exchange)

    def execute(self, order: Any):
        platform = self._platform(order)

        self.guard.validate(
            order,
            self._policy_provider(),
        )

        adapter = self.adapter(platform)
        return adapter.place_order(order)

    def cancel(self, exchange: str, order: Any):
        adapter = self.adapter(exchange)
        return adapter.cancel_order(order)

    def get_balance(self, exchange: str):
        adapter = self.adapter(exchange)
        return adapter.get_balance()

    def get_positions(self, exchange: str):
        adapter = self.adapter(exchange)
        return adapter.get_positions()

    def health(self, exchange: str):
        adapter = self.adapter(exchange)
        return adapter.health()


exchange_manager = ExchangeManager()
