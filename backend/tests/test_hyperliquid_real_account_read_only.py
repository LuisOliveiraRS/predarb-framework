from __future__ import annotations

import ast
from pathlib import Path
from typing import Any

import pytest

from app.clients.hyperliquid import (
    HyperliquidClient,
)


USER = (
    "0x"
    "ABCDEFabcdef"
    "0123456789"
    "ABCDEFabcdef"
    "012345"
)

NORMALIZED_USER = USER.lower()

assert len(USER) == 42
assert len(USER[2:]) == 40


class FakeHttpClient:
    def __init__(
        self,
        responses: list[Any],
    ) -> None:
        self.responses = list(
            responses
        )
        self.calls: list[
            tuple[str, dict[str, Any]]
        ] = []
        self.closed = False

    async def post(
        self,
        url: str,
        payload: dict[str, Any],
    ) -> Any:
        self.calls.append(
            (
                url,
                payload,
            )
        )

        return self.responses.pop(
            0
        )

    async def close(
        self,
    ) -> None:
        self.closed = True


def build_client(
    *responses: Any,
) -> tuple[
    HyperliquidClient,
    FakeHttpClient,
]:
    http = FakeHttpClient(
        list(responses)
    )

    client = HyperliquidClient(
        base_url=(
            "https://api.hyperliquid.xyz"
        ),
        client=http,
    )

    return client, http


def test_normalize_public_address():
    assert (
        HyperliquidClient
        .normalize_user_address(
            f"  {USER}  "
        )
        == NORMALIZED_USER
    )


@pytest.mark.parametrize(
    "value",
    [
        "",
        "0x1234",
        "1234567890",
        (
            "0x"
            + ("z" * 40)
        ),
    ],
)
def test_invalid_public_address_is_rejected(
    value,
):
    with pytest.raises(
        ValueError
    ):
        (
            HyperliquidClient
            .normalize_user_address(
                value
            )
        )


@pytest.mark.asyncio
async def test_reads_perpetual_positions_and_margin():
    client, http = build_client(
        {
            "marginSummary": {
                "accountValue": "100.00",
            },
            "assetPositions": [],
        }
    )

    result = await client.clearinghouse_state(
        USER,
        dex="test",
    )

    assert result["assetPositions"] == []

    assert http.calls == [
        (
            "https://api.hyperliquid.xyz/info",
            {
                "type": "clearinghouseState",
                "user": NORMALIZED_USER,
                "dex": "test",
            },
        )
    ]


@pytest.mark.asyncio
async def test_reads_spot_balances():
    client, http = build_client(
        {
            "balances": [
                {
                    "coin": "USDC",
                    "total": "100.0",
                }
            ]
        }
    )

    result = (
        await client
        .spot_clearinghouse_state(
            USER
        )
    )

    assert len(
        result["balances"]
    ) == 1

    assert http.calls[0][1] == {
        "type": (
            "spotClearinghouseState"
        ),
        "user": NORMALIZED_USER,
    }


@pytest.mark.asyncio
async def test_reads_open_orders():
    client, http = build_client(
        [
            {
                "coin": "BTC",
                "oid": 123,
            }
        ]
    )

    result = await client.open_orders(
        USER
    )

    assert result == [
        {
            "coin": "BTC",
            "oid": 123,
        }
    ]

    assert http.calls[0][1] == {
        "type": "openOrders",
        "user": NORMALIZED_USER,
    }


@pytest.mark.asyncio
async def test_reads_user_fills():
    client, http = build_client(
        [
            {
                "coin": "ETH",
                "oid": 456,
            }
        ]
    )

    result = await client.user_fills(
        USER,
        aggregate_by_time=False,
    )

    assert result[0]["oid"] == 456

    assert http.calls[0][1] == {
        "type": "userFills",
        "user": NORMALIZED_USER,
        "aggregateByTime": False,
    }


@pytest.mark.asyncio
async def test_reads_portfolio_and_user_role():
    client, http = build_client(
        [
            [
                "day",
                {
                    "vlm": "0.0",
                },
            ]
        ],
        {
            "role": "user",
        },
    )

    portfolio = await client.portfolio(
        USER
    )

    role = await client.user_role(
        USER
    )

    assert portfolio[0][0] == "day"
    assert role == {
        "role": "user",
    }

    assert [
        call[1]["type"]
        for call in http.calls
    ] == [
        "portfolio",
        "userRole",
    ]


@pytest.mark.asyncio
async def test_invalid_response_formats_fail_closed():
    client, _ = build_client(
        [],
        {},
    )

    with pytest.raises(
        TypeError
    ):
        await client.clearinghouse_state(
            USER
        )

    with pytest.raises(
        TypeError
    ):
        await client.open_orders(
            USER
        )


def test_client_remains_strictly_read_only():
    path = Path(
        "app/clients/hyperliquid.py"
    )

    source = path.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    prohibited_identifiers = {
        "exchange",
        "order",
        "cancel",
        "withdraw",
        "transfer",
        "sign",
        "signature",
        "private_key",
        "api_secret",
        "submit_order",
    }

    allowed_method_names = {
        "open_orders",
    }

    for node in ast.walk(
        tree
    ):
        if isinstance(
            node,
            ast.FunctionDef,
        ):
            if (
                node.name
                in allowed_method_names
            ):
                continue

            assert (
                node.name
                not in prohibited_identifiers
            )

        if isinstance(
            node,
            ast.AsyncFunctionDef,
        ):
            if (
                node.name
                in allowed_method_names
            ):
                continue

            assert (
                node.name
                not in prohibited_identifiers
            )

        if isinstance(
            node,
            ast.Constant,
        ) and isinstance(
            node.value,
            str,
        ):
            normalized = (
                node.value.lower()
            )

            assert "/exchange" not in normalized
            assert "private_key" not in normalized
            assert "api_secret" not in normalized
