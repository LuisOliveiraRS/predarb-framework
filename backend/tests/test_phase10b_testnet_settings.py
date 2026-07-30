import pytest

from app.core.settings import Settings


def make_settings(**changes):
    values = {
        "HYPERLIQUID_TESTNET_API_URL":
            "https://api.hyperliquid-testnet.xyz",
        "HYPERLIQUID_TESTNET_EXECUTION_ENABLED": False,
        "HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED": False,
        "HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL": 10.0,
        "HYPERLIQUID_MAINNET_EXECUTION_ENABLED": False,
        "HYPERLIQUID_MAINNET_EXECUTION_AUTHORIZED": False,
    }
    values.update(changes)
    return Settings(_env_file=None, **values)


def test_testnet_execution_is_disabled_by_default():
    configured = make_settings()

    assert configured.HYPERLIQUID_TESTNET_EXECUTION_ENABLED is False
    assert configured.HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED is False


@pytest.mark.parametrize(
    "field",
    [
        "HYPERLIQUID_MAINNET_EXECUTION_ENABLED",
        "HYPERLIQUID_MAINNET_EXECUTION_AUTHORIZED",
    ],
)
def test_mainnet_execution_flags_are_rejected(field):
    with pytest.raises(ValueError):
        make_settings(**{field: True})


def test_testnet_authorization_requires_enabled_execution():
    with pytest.raises(ValueError):
        make_settings(
            HYPERLIQUID_TESTNET_EXECUTION_AUTHORIZED=True,
        )


def test_non_official_testnet_url_is_rejected():
    with pytest.raises(ValueError):
        make_settings(
            HYPERLIQUID_TESTNET_API_URL=
                "https://api.hyperliquid.xyz",
        )


def test_testnet_notional_limit_must_be_positive():
    with pytest.raises(ValueError):
        make_settings(
            HYPERLIQUID_TESTNET_MAX_ORDER_NOTIONAL=0,
        )
