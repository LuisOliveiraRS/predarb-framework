from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.providers.hyperliquid_provider import (
    HyperliquidProvider,
)


USER = (
    "0x"
    + ("a" * 40)
)


class FakeAccountClient:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            tuple[str, dict[str, Any]]
        ] = []

    @staticmethod
    def normalize_user_address(
        user: str,
    ) -> str:
        normalized = user.strip().lower()

        if len(normalized) != 42:
            raise ValueError(
                "invalid address"
            )

        return normalized

    async def user_role(
        self,
        user: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "user_role",
                {
                    "user": user,
                },
            )
        )

        return {
            "role": "user",
        }

    async def clearinghouse_state(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "clearinghouse_state",
                {
                    "user": user,
                    "dex": dex,
                },
            )
        )

        return {
            "marginSummary": {
                "accountValue": "250.00",
            },
            "assetPositions": [
                {
                    "position": {
                        "coin": "BTC",
                    },
                }
            ],
        }

    async def spot_clearinghouse_state(
        self,
        user: str,
    ) -> dict[str, Any]:
        self.calls.append(
            (
                "spot_clearinghouse_state",
                {
                    "user": user,
                },
            )
        )

        return {
            "balances": [
                {
                    "coin": "USDC",
                    "total": "100.00",
                }
            ],
        }

    async def open_orders(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "open_orders",
                {
                    "user": user,
                    "dex": dex,
                },
            )
        )

        return [
            {
                "coin": "BTC",
                "oid": 123,
            }
        ]

    async def user_fills(
        self,
        user: str,
        *,
        aggregate_by_time: bool = True,
    ) -> list[dict[str, Any]]:
        self.calls.append(
            (
                "user_fills",
                {
                    "user": user,
                    "aggregate_by_time": (
                        aggregate_by_time
                    ),
                },
            )
        )

        return [
            {
                "coin": "ETH",
                "oid": 456,
            }
        ]

    async def portfolio(
        self,
        user: str,
    ) -> list[Any]:
        self.calls.append(
            (
                "portfolio",
                {
                    "user": user,
                },
            )
        )

        return [
            [
                "day",
                {
                    "vlm": "10.0",
                },
            ]
        ]

    async def close(
        self,
    ) -> None:
        return None


@pytest.mark.asyncio
async def test_provider_builds_real_read_only_snapshot():
    client = FakeAccountClient()

    provider = HyperliquidProvider(
        client=client
    )

    snapshot = (
        await provider
        .get_account_snapshot(
            USER.upper(),
            dex="hip4",
        )
    )

    assert snapshot["status"] == "online"

    assert (
        snapshot["account_address"]
        == USER
    )

    assert snapshot["dex"] == "hip4"

    assert snapshot["role"] == {
        "role": "user",
    }

    assert (
        snapshot["summary"][
            "perpetual_positions"
        ]
        == 1
    )

    assert (
        snapshot["summary"][
            "spot_balances"
        ]
        == 1
    )

    assert (
        snapshot["summary"][
            "open_orders"
        ]
        == 1
    )

    assert snapshot["summary"]["fills"] == 1

    assert (
        snapshot["summary"][
            "portfolio_entries"
        ]
        == 1
    )

    assert snapshot["latency"] >= 0


@pytest.mark.asyncio
async def test_provider_uses_only_read_account_methods():
    client = FakeAccountClient()

    provider = HyperliquidProvider(
        client=client
    )

    await provider.get_account_snapshot(
        USER,
        dex="hip4",
    )

    assert [
        name
        for name, _ in client.calls
    ] == [
        "user_role",
        "clearinghouse_state",
        "spot_clearinghouse_state",
        "open_orders",
        "user_fills",
        "portfolio",
    ]


@pytest.mark.asyncio
async def test_provider_snapshot_keeps_execution_disabled():
    provider = HyperliquidProvider(
        client=FakeAccountClient()
    )

    snapshot = (
        await provider
        .get_account_snapshot(
            USER
        )
    )

    protected_flags = (
        "wallet_signing",
        "private_key_access",
        "credential_access",
        "exchange_endpoint_available",
        "order_submission_available",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "automatic_execution_authorized",
        "next_step_authorized",
    )

    for flag in protected_flags:
        assert snapshot[flag] is False

    assert snapshot["read_only"] is True

    assert (
        snapshot["public_address_only"]
        is True
    )


def test_provider_has_no_exchange_or_secret_access():
    path = Path(
        "app/providers/"
        "hyperliquid_provider.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    prohibited_names = {
        "private_key",
        "api_secret",
        "wallet_secret",
        "sign",
        "sign_transaction",
        "submit_order",
        "place_order",
        "cancel_order",
        "withdraw",
        "transfer",
    }

    prohibited_modules = (
        "eth_account",
        "web3",
        "app.orders",
        "app.oms",
        "app.trading",
    )

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            (
                ast.FunctionDef,
                ast.AsyncFunctionDef,
            ),
        ):
            assert (
                node.name
                not in prohibited_names
            )

        if isinstance(
            node,
            ast.Name,
        ):
            assert (
                node.id
                not in prohibited_names
            )

        if isinstance(
            node,
            ast.Attribute,
        ):
            assert (
                node.attr
                not in prohibited_names
            )

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                assert not alias.name.startswith(
                    prohibited_modules
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            module = node.module or ""

            assert not module.startswith(
                prohibited_modules
            )

        if (
            isinstance(
                node,
                ast.Constant,
            )
            and isinstance(
                node.value,
                str,
            )
        ):
            normalized = (
                node.value.lower()
            )

            assert "/exchange" not in normalized

    assert tree is not None
