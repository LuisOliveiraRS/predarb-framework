"""Fase 18 - registry fail-closed e mocks sem rede."""

import asyncio
from decimal import Decimal

import pytest

from app.crypto_arbitrage.connectors.base import (
    PublicCexConnector,
)
from app.crypto_arbitrage.connectors.registry import (
    ConnectorRegistry,
    assert_no_execution_capability,
)
from app.crypto_arbitrage.domain.enums import (
    ConnectorState,
    InstrumentStatus,
    Side,
)
from app.crypto_arbitrage.domain.errors import (
    ConnectorAlreadyRegisteredError,
    ConnectorNotFoundError,
    ExecutionNotAuthorizedError,
)
from app.crypto_arbitrage.mocks.public_cex import (
    MockPublicCexConnector,
)


class ConnectorWithExecution:
    """Simula um adapter capaz de enviar ordem."""

    venue_id = "EVIL"

    async def submit_order(self, intent, authorization):
        raise AssertionError(
            "Nunca deve ser chamado."
        )


class ConnectorWithWithdraw:
    venue_id = "EVIL2"

    def withdraw(self, *args, **kwargs):
        raise AssertionError(
            "Nunca deve ser chamado."
        )


def test_registry_refuses_connector_that_can_submit_order():
    registry = ConnectorRegistry()

    with pytest.raises(ExecutionNotAuthorizedError):
        registry.register_public(
            ConnectorWithExecution()
        )


def test_registry_refuses_connector_that_can_withdraw():
    registry = ConnectorRegistry()

    with pytest.raises(ExecutionNotAuthorizedError):
        registry.register_public(
            ConnectorWithWithdraw()
        )


def test_registering_trading_adapter_is_always_refused():
    registry = ConnectorRegistry()

    with pytest.raises(ExecutionNotAuthorizedError):
        registry.register_trading_adapter(
            MockPublicCexConnector("BINANCE")
        )


def test_capability_guard_lists_offending_methods():
    with pytest.raises(
        ExecutionNotAuthorizedError
    ) as excinfo:
        assert_no_execution_capability(
            ConnectorWithExecution()
        )

    assert "submit_order" in str(excinfo.value)


def test_registry_accepts_read_only_connector():
    registry = ConnectorRegistry()
    connector = MockPublicCexConnector("BINANCE")

    registry.register_public(connector)

    assert registry.public_venues() == ["BINANCE"]
    assert (
        registry.get_public("binance") is connector
    )


def test_registry_rejects_duplicate_venue():
    registry = ConnectorRegistry()

    registry.register_public(
        MockPublicCexConnector("BINANCE")
    )

    with pytest.raises(
        ConnectorAlreadyRegisteredError
    ):
        registry.register_public(
            MockPublicCexConnector("BINANCE")
        )


def test_registry_raises_for_unknown_venue():
    registry = ConnectorRegistry()

    with pytest.raises(ConnectorNotFoundError):
        registry.get_public("OKX")


def test_registry_status_declares_safety_flags():
    registry = ConnectorRegistry()

    registry.register_public(
        MockPublicCexConnector("BINANCE")
    )

    status = registry.status()

    assert status["trading_adapters"] == []
    assert status["read_only"] is True
    assert status["market_data_only"] is True
    assert status["execution_authorized"] is False
    assert status["financial_execution"] is False
    assert (
        status["automatic_execution_authorized"] is False
    )
    assert status["order_submission_available"] is False
    assert status["exchange_endpoint_available"] is False
    assert status["wallet_signing"] is False
    assert status["private_key_access"] is False


def test_mock_satisfies_public_protocol():
    connector = MockPublicCexConnector("BINANCE")

    assert isinstance(connector, PublicCexConnector)


def test_mock_has_no_execution_methods():
    connector = MockPublicCexConnector("BINANCE")

    assert_no_execution_capability(connector)

    for forbidden in (
        "submit_order",
        "cancel_order",
        "withdraw",
        "sign_transaction",
    ):
        assert not hasattr(connector, forbidden)


def test_mock_lists_tradable_instruments():
    connector = MockPublicCexConnector(
        "BINANCE",
        symbols={
            "BTCUSDT": Decimal("60000"),
            "ETHUSDT": Decimal("3000"),
        },
    )

    instruments = asyncio.run(
        connector.list_instruments()
    )

    assert [
        item.instrument_id for item in instruments
    ] == ["BTCUSDT", "ETHUSDT"]

    assert all(
        item.status is InstrumentStatus.TRADING
        for item in instruments
    )


def test_mock_book_is_deterministic_and_usable():
    connector = MockPublicCexConnector("BINANCE")

    first = asyncio.run(
        connector.get_order_book("BTCUSDT", 3)
    )

    second = asyncio.run(
        connector.get_order_book("btcusdt", 3)
    )

    assert first.bids == second.bids
    assert first.asks == second.asks
    assert first.best_bid.price < first.best_ask.price

    result = first.vwap_for_quantity(
        Side.BUY,
        Decimal("0.5"),
    )

    assert result.filled_quantity == Decimal("0.5")
    assert result.vwap > Decimal("0")


def test_mock_rejects_unknown_instrument():
    connector = MockPublicCexConnector("BINANCE")

    with pytest.raises(KeyError):
        asyncio.run(
            connector.get_order_book("DOGEUSDT", 3)
        )


def test_mock_health_reports_state():
    connector = MockPublicCexConnector(
        "BINANCE",
        state=ConnectorState.DEGRADED,
    )

    health = asyncio.run(connector.health())

    assert health.state is ConnectorState.DEGRADED
    assert health.to_dict()["is_usable"] is False


def test_connector_state_only_ready_is_usable():
    assert ConnectorState.READY.is_usable is True

    for state in (
        ConnectorState.DISCONNECTED,
        ConnectorState.CONNECTING,
        ConnectorState.DEGRADED,
        ConnectorState.STALE,
    ):
        assert state.is_usable is False


def test_stream_yields_snapshots_without_network():
    connector = MockPublicCexConnector(
        "BINANCE",
        symbols={
            "BTCUSDT": Decimal("60000"),
            "ETHUSDT": Decimal("3000"),
        },
    )

    async def collect():
        return [
            snapshot
            async for snapshot in (
                connector.stream_order_books(
                    ["BTCUSDT", "ETHUSDT"]
                )
            )
        ]

    snapshots = asyncio.run(collect())

    assert len(snapshots) == 2
    assert {
        snapshot.instrument_id
        for snapshot in snapshots
    } == {"BTCUSDT", "ETHUSDT"}
