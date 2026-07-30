from types import SimpleNamespace

import pytest

from app.execution.testnet_guard import (
    ExecutionGuardError,
    HYPERLIQUID_TESTNET_API_URL,
    HyperliquidTestnetGuard,
    TestnetExecutionPolicy,
)


def order(
    platform="hyperliquid-testnet",
    quantity=2,
    price=3,
    environment="testnet",
):
    return SimpleNamespace(
        platform=platform,
        quantity=quantity,
        price=price,
        mode=environment.upper(),
        metadata={"environment": environment},
    )


def policy(**changes):
    values = {
        "enabled": True,
        "execution_authorized": True,
        "max_order_notional": 10.0,
        "api_url": HYPERLIQUID_TESTNET_API_URL,
    }
    values.update(changes)
    return TestnetExecutionPolicy(**values)


def test_paper_remains_available():
    result = HyperliquidTestnetGuard().validate(
        order(platform="paper"),
        TestnetExecutionPolicy(),
    )
    assert result["environment"] == "paper"
    assert result["financial_execution"] is False


@pytest.mark.parametrize(
    "platform",
    ["hyperliquid", "mainnet", "binance"],
)
def test_non_testnet_platform_is_blocked(platform):
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(platform=platform),
            policy(),
        )


def test_disabled_testnet_is_blocked():
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(),
            policy(enabled=False),
        )


def test_missing_authorization_is_blocked():
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(),
            policy(execution_authorized=False),
        )


def test_mainnet_url_is_blocked():
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(),
            policy(api_url="https://api.hyperliquid.xyz"),
        )


def test_missing_testnet_environment_is_blocked():
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(environment="mainnet"),
            policy(),
        )


def test_notional_above_limit_is_blocked():
    with pytest.raises(ExecutionGuardError):
        HyperliquidTestnetGuard().validate(
            order(quantity=3, price=4),
            policy(max_order_notional=10),
        )


def test_valid_testnet_order_is_approved():
    result = HyperliquidTestnetGuard().validate(
        order(quantity=2, price=3),
        policy(),
    )

    assert result["approved"] is True
    assert result["environment"] == "testnet"
    assert result["notional"] == 6
    assert result["mainnet"] is False
    assert result["financial_execution"] is False
