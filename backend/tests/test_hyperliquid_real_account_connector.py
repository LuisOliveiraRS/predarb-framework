from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.connectors.hyperliquid.connector import (
    HyperliquidConnector,
)


USER = (
    "0x"
    + ("b" * 40)
)


class FakeProvider:
    def __init__(
        self,
    ) -> None:
        self.calls: list[
            dict[str, Any]
        ] = []

    async def get_account_snapshot(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> dict[str, Any]:
        self.calls.append(
            {
                "user": user,
                "dex": dex,
            }
        )

        return {
            "status": "online",
            "connector": "hyperliquid",
            "account_address": user.lower(),
            "dex": dex,
            "summary": {
                "perpetual_positions": 1,
                "spot_balances": 2,
                "open_orders": 0,
                "fills": 3,
                "portfolio_entries": 4,
            },
            "read_only": True,
            "public_address_only": True,
            "wallet_signing": False,
            "private_key_access": False,
            "credential_access": False,
            "exchange_endpoint_available": False,
            "order_submission_available": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "automatic_execution_authorized": False,
            "next_step_authorized": False,
        }

    async def health(
        self,
    ) -> dict[str, Any]:
        return {
            "status": "online",
            "connected": True,
        }

    async def close(
        self,
    ) -> None:
        return None

    async def get_all_markets(
        self,
    ) -> dict[str, Any]:
        return {
            "metadata": {
                "outcomes": [],
            },
            "mids": {},
        }


class FakeParser:
    def parse(
        self,
        snapshot: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return []


@pytest.mark.asyncio
async def test_connector_delegates_account_snapshot():
    provider = FakeProvider()

    connector = HyperliquidConnector(
        provider=provider,
        parser=FakeParser(),
    )

    snapshot = (
        await connector
        .get_account_snapshot(
            USER.upper(),
            dex="hip4",
        )
    )

    assert provider.calls == [
        {
            "user": USER.upper(),
            "dex": "hip4",
        }
    ]

    assert snapshot[
        "account_address"
    ] == USER

    assert snapshot["read_only"] is True
    assert connector.connected is True


@pytest.mark.asyncio
async def test_connector_exposes_safe_account_details():
    connector = HyperliquidConnector(
        provider=FakeProvider(),
        parser=FakeParser(),
    )

    await connector.get_account_snapshot(
        USER
    )

    details = connector._last_details

    assert (
        details["account_read_only"]
        is True
    )

    assert details[
        "account_summary"
    ] == {
        "perpetual_positions": 1,
        "spot_balances": 2,
        "open_orders": 0,
        "fills": 3,
        "portfolio_entries": 4,
    }

    protected_flags = (
        "wallet_signing",
        "private_key_access",
        "credential_access",
        "exchange_endpoint_available",
        "order_submission_available",
        "execution_authorized",
        "live_execution",
        "financial_execution",
    )

    for flag in protected_flags:
        assert details[flag] is False


@pytest.mark.asyncio
async def test_connector_fails_closed_on_provider_error():
    class FailingProvider(
        FakeProvider
    ):
        async def get_account_snapshot(
            self,
            user: str,
            *,
            dex: str = "",
        ) -> dict[str, Any]:
            raise RuntimeError(
                "account unavailable"
            )

    connector = HyperliquidConnector(
        provider=FailingProvider(),
        parser=FakeParser(),
    )

    with pytest.raises(
        RuntimeError,
        match="account unavailable",
    ):
        await connector.get_account_snapshot(
            USER
        )

    assert connector.connected is False

    status = connector.get_status()

    assert (
        "account unavailable"
        in str(status.error)
    )


def test_connector_has_no_execution_implementation():
    path = Path(
        "app/connectors/hyperliquid/"
        "connector.py"
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
        "sign",
        "signature",
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
            assert (
                "/exchange"
                not in node.value.lower()
            )
