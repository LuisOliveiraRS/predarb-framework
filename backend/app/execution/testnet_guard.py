from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any, Mapping


HYPERLIQUID_TESTNET_API_URL = (
    "https://api.hyperliquid-testnet.xyz"
)


class ExecutionGuardError(RuntimeError):
    """Bloqueio operacional de execução."""


@dataclass(frozen=True, slots=True)
class TestnetExecutionPolicy:
    __test__ = False
    enabled: bool = False
    execution_authorized: bool = False
    max_order_notional: float = 10.0
    api_url: str = HYPERLIQUID_TESTNET_API_URL


def _value(order: Any, name: str, default: Any = None) -> Any:
    if isinstance(order, Mapping):
        return order.get(name, default)
    return getattr(order, name, default)


class HyperliquidTestnetGuard:
    """Autoriza somente ordens explicitamente destinadas à testnet."""

    def validate(
        self,
        order: Any,
        policy: TestnetExecutionPolicy,
    ) -> dict[str, Any]:
        platform = str(
            _value(order, "platform", "")
        ).strip().lower()

        if platform == "paper":
            return {
                "approved": True,
                "environment": "paper",
                "financial_execution": False,
            }

        if platform != "hyperliquid-testnet":
            raise ExecutionGuardError(
                "Somente paper ou hyperliquid-testnet são permitidos."
            )

        if not policy.enabled:
            raise ExecutionGuardError(
                "Execução Hyperliquid testnet está desabilitada."
            )

        if not policy.execution_authorized:
            raise ExecutionGuardError(
                "Execução testnet exige autorização explícita."
            )

        api_url = str(policy.api_url or "").strip().rstrip("/")

        if api_url != HYPERLIQUID_TESTNET_API_URL:
            raise ExecutionGuardError(
                "A URL configurada não corresponde à testnet oficial."
            )

        metadata = _value(order, "metadata", {}) or {}
        mode = str(_value(order, "mode", "") or "").strip().lower()

        if isinstance(metadata, Mapping):
            environment = str(
                metadata.get("environment", mode)
            ).strip().lower()
        else:
            environment = mode

        if environment != "testnet":
            raise ExecutionGuardError(
                "A ordem deve declarar environment=testnet."
            )

        try:
            quantity = float(_value(order, "quantity", 0))
            price = float(_value(order, "price", 0))
            maximum = float(policy.max_order_notional)
        except (TypeError, ValueError) as exc:
            raise ExecutionGuardError(
                "Quantidade, preço e limite devem ser numéricos."
            ) from exc

        values = (quantity, price, maximum)

        if not all(isfinite(value) for value in values):
            raise ExecutionGuardError(
                "Valores não finitos são proibidos."
            )

        if quantity <= 0 or price <= 0 or maximum <= 0:
            raise ExecutionGuardError(
                "Quantidade, preço e limite devem ser positivos."
            )

        notional = round(quantity * price, 8)

        if notional > maximum:
            raise ExecutionGuardError(
                "Valor nocional excede o limite da testnet."
            )

        return {
            "approved": True,
            "environment": "testnet",
            "platform": platform,
            "notional": notional,
            "max_order_notional": maximum,
            "mainnet": False,
            "financial_execution": False,
        }


hyperliquid_testnet_guard = HyperliquidTestnetGuard()
