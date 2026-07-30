from types import SimpleNamespace

import pytest

from app.execution.testnet_guard import (
    ExecutionGuardError,
    HYPERLIQUID_TESTNET_API_URL,
    TestnetExecutionPolicy,
)
from app.exchanges.exchange_manager import ExchangeManager


class FakeAdapter:
    def __init__(self):
        self.calls = 0

    def place_order(self, order):
        self.calls += 1
        return {"accepted": True}


class FakeRegistry:
    def __init__(self, adapter):
        self.adapter = adapter
        self.get_calls = 0

    def get(self, name):
        self.get_calls += 1
        return self.adapter


def make_order(
    platform,
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


def make_policy(**changes):
    values = {
        "enabled": True,
        "execution_authorized": True,
        "max_order_notional": 10.0,
        "api_url": HYPERLIQUID_TESTNET_API_URL,
    }
    values.update(changes)
    return TestnetExecutionPolicy(**values)


def make_manager(policy):
    adapter = FakeAdapter()
    registry = FakeRegistry(adapter)

    manager = ExchangeManager(
        registry=registry,
        policy_provider=lambda: policy,
    )

    return manager, registry, adapter


def test_paper_execution_remains_available():
    manager, registry, adapter = make_manager(
        TestnetExecutionPolicy()
    )

    result = manager.execute(
        make_order("paper", environment="paper")
    )

    assert result == {"accepted": True}
    assert registry.get_calls == 1
    assert adapter.calls == 1


def test_mainnet_is_blocked_before_adapter_lookup():
    manager, registry, adapter = make_manager(
        make_policy()
    )

    with pytest.raises(ExecutionGuardError):
        manager.execute(
            make_order("hyperliquid")
        )

    assert registry.get_calls == 0
    assert adapter.calls == 0


def test_disabled_testnet_is_blocked_before_adapter():
    manager, registry, adapter = make_manager(
        make_policy(enabled=False)
    )

    with pytest.raises(ExecutionGuardError):
        manager.execute(
            make_order("hyperliquid-testnet")
        )

    assert registry.get_calls == 0
    assert adapter.calls == 0


def test_testnet_notional_limit_is_enforced():
    manager, registry, adapter = make_manager(
        make_policy(max_order_notional=5)
    )

    with pytest.raises(ExecutionGuardError):
        manager.execute(
            make_order(
                "hyperliquid-testnet",
                quantity=2,
                price=3,
            )
        )

    assert registry.get_calls == 0
    assert adapter.calls == 0


def test_authorized_testnet_reaches_fake_adapter():
    manager, registry, adapter = make_manager(
        make_policy()
    )

    result = manager.execute(
        make_order(
            "hyperliquid-testnet",
            quantity=2,
            price=3,
        )
    )

    assert result == {"accepted": True}
    assert registry.get_calls == 1
    assert adapter.calls == 1
