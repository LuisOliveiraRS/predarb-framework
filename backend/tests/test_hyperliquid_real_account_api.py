from __future__ import annotations

import pytest
from fastapi import HTTPException

from app.api.routers.connectors import (
    hyperliquid_account_snapshot,
    router,
)
from app.connectors.manager.connector_manager import (
    connector_manager,
)


USER = "0x" + ("c" * 40)


class FakeConnector:
    async def get_account_snapshot(
        self,
        user: str,
        *,
        dex: str = "",
    ):
        return {
            "status": "online",
            "account_address": user.lower(),
            "dex": dex,
            "read_only": True,
            "public_address_only": True,
            "wallet_signing": False,
            "private_key_access": False,
            "order_submission_available": False,
            "execution_authorized": False,
            "financial_execution": False,
        }


@pytest.mark.asyncio
async def test_account_route_returns_safe_snapshot(
    monkeypatch,
):
    connector = FakeConnector()

    monkeypatch.setattr(
        connector_manager,
        "exists",
        lambda name: name == "hyperliquid",
    )

    monkeypatch.setattr(
        connector_manager,
        "require",
        lambda name: connector,
    )

    result = (
        await hyperliquid_account_snapshot(
            USER.upper(),
            dex="hip4",
        )
    )

    assert result["account_address"] == USER
    assert result["dex"] == "hip4"
    assert result["read_only"] is True
    assert result["wallet_signing"] is False
    assert result[
        "order_submission_available"
    ] is False
    assert result[
        "financial_execution"
    ] is False


@pytest.mark.asyncio
async def test_account_route_rejects_invalid_address(
    monkeypatch,
):
    class InvalidConnector:
        async def get_account_snapshot(
            self,
            user: str,
            *,
            dex: str = "",
        ):
            raise ValueError(
                "invalid address"
            )

    monkeypatch.setattr(
        connector_manager,
        "exists",
        lambda name: True,
    )

    monkeypatch.setattr(
        connector_manager,
        "require",
        lambda name: InvalidConnector(),
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await hyperliquid_account_snapshot(
            "invalid"
        )

    assert exc.value.status_code == 422


@pytest.mark.asyncio
async def test_account_route_requires_connector(
    monkeypatch,
):
    monkeypatch.setattr(
        connector_manager,
        "exists",
        lambda name: False,
    )

    with pytest.raises(
        HTTPException
    ) as exc:
        await hyperliquid_account_snapshot(
            USER
        )

    assert exc.value.status_code == 503


def test_account_route_is_get_and_precedes_dynamic_route():
    routes = list(
        router.routes
    )

    account_index = next(
        index
        for index, route in enumerate(routes)
        if route.path.endswith(
            "/hyperliquid/account/{user}"
        )
    )

    dynamic_index = next(
        index
        for index, route in enumerate(routes)
        if route.path.endswith(
            "/{connector_name}"
        )
    )

    account_route = routes[
        account_index
    ]

    assert account_route.methods == {
        "GET"
    }

    assert account_index < dynamic_index
