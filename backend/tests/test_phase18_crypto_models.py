"""Fase 18 - modelos de book, oportunidade e plano."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.domain.enums import (
    ExecutionMode,
    InstrumentStatus,
    MarketType,
    OrderType,
    RiskStatus,
    Side,
    StrategyType,
)
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    InsufficientDepthError,
    StaleMarketDataError,
)
from app.crypto_arbitrage.domain.models import (
    ExecutionPlan,
    Instrument,
    Opportunity,
    OrderBookLevel,
    OrderBookSnapshot,
    OrderIntent,
    RiskDecision,
)
from app.crypto_arbitrage.domain.symbols import build_pair


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)

PAIR = build_pair("BTC", "USDT")


def _book(**overrides) -> OrderBookSnapshot:
    payload = {
        "venue_id": "BINANCE",
        "instrument_id": "BTCUSDT",
        "bids": (
            OrderBookLevel(
                price=Decimal("100"),
                quantity=Decimal("1"),
            ),
            OrderBookLevel(
                price=Decimal("99"),
                quantity=Decimal("2"),
            ),
        ),
        "asks": (
            OrderBookLevel(
                price=Decimal("101"),
                quantity=Decimal("1"),
            ),
            OrderBookLevel(
                price=Decimal("102"),
                quantity=Decimal("2"),
            ),
        ),
        "exchange_timestamp": MOMENT,
        "received_timestamp": MOMENT,
    }

    payload.update(overrides)

    return OrderBookSnapshot(**payload)


def test_instrument_defaults_to_unknown_status():
    instrument = Instrument(
        venue_id="BINANCE",
        instrument_id="BTCUSDT",
        pair=PAIR,
        market_type=MarketType.SPOT,
        price_tick=Decimal("0.01"),
        quantity_step=Decimal("0.001"),
        min_quantity=Decimal("0.001"),
        min_notional=Decimal("10"),
    )

    assert instrument.status is InstrumentStatus.UNKNOWN
    assert instrument.is_tradable is False


def test_instrument_rejects_non_positive_tick():
    with pytest.raises(DomainValidationError):
        Instrument(
            venue_id="BINANCE",
            instrument_id="BTCUSDT",
            pair=PAIR,
            market_type=MarketType.SPOT,
            price_tick=Decimal("0"),
            quantity_step=Decimal("0.001"),
            min_quantity=Decimal("0.001"),
            min_notional=Decimal("10"),
        )


def test_book_rejects_unordered_levels():
    with pytest.raises(DomainValidationError):
        _book(
            bids=(
                OrderBookLevel(
                    price=Decimal("99"),
                    quantity=Decimal("1"),
                ),
                OrderBookLevel(
                    price=Decimal("100"),
                    quantity=Decimal("1"),
                ),
            )
        )


def test_book_rejects_crossed_market():
    with pytest.raises(DomainValidationError):
        _book(
            bids=(
                OrderBookLevel(
                    price=Decimal("105"),
                    quantity=Decimal("1"),
                ),
            )
        )


def test_book_requires_timezone_aware_timestamps():
    with pytest.raises(DomainValidationError):
        _book(received_timestamp=datetime(2026, 8, 2))


def test_mid_price_and_best_levels():
    book = _book()

    assert book.best_bid.price == Decimal("100")
    assert book.best_ask.price == Decimal("101")
    assert book.mid_price == Decimal("100.5")


def test_vwap_buy_consumes_asks_across_levels():
    book = _book()

    result = book.vwap_for_quantity(
        Side.BUY,
        Decimal("2"),
    )

    # 1 @ 101 + 1 @ 102 = 203, dividido por 2.
    assert result.notional == Decimal("203")
    assert result.vwap == Decimal("101.5")
    assert result.levels_consumed == 2


def test_vwap_sell_consumes_bids():
    book = _book()

    result = book.vwap_for_quantity(
        Side.SELL,
        Decimal("1"),
    )

    assert result.vwap == Decimal("100")
    assert result.levels_consumed == 1


def test_vwap_blocks_when_depth_is_insufficient():
    book = _book()

    with pytest.raises(InsufficientDepthError):
        book.vwap_for_quantity(
            Side.BUY,
            Decimal("10"),
        )


def test_book_age_and_staleness():
    book = _book()
    later = MOMENT + timedelta(milliseconds=500)

    assert book.age_ms(later) == Decimal("500")
    assert book.is_stale(later, Decimal("200")) is True
    assert book.is_stale(later, Decimal("800")) is False


def test_require_fresh_raises_for_stale_book():
    book = _book()
    later = MOMENT + timedelta(seconds=5)

    with pytest.raises(StaleMarketDataError):
        book.require_fresh(later, Decimal("1000"))


def _opportunity(**overrides) -> Opportunity:
    payload = {
        "strategy_type": StrategyType.CEX_CEX_SPATIAL,
        "buy_venue_id": "BINANCE",
        "sell_venue_id": "OKX",
        "pair": PAIR,
        "requested_quantity": Decimal("1"),
        "executable_quantity": Decimal("1"),
        "buy_vwap": Decimal("100"),
        "sell_vwap": Decimal("110"),
        "total_fees": Decimal("2"),
        "safety_buffer": Decimal("1"),
        "observed_at": MOMENT,
    }

    payload.update(overrides)

    return Opportunity(**payload)


def test_opportunity_starts_blocked_and_not_executable():
    opportunity = _opportunity()

    assert opportunity.risk_status is RiskStatus.BLOCKED
    assert opportunity.is_executable is False


def test_opportunity_net_profit_discounts_fees_and_buffer():
    opportunity = _opportunity()

    assert opportunity.gross_profit == Decimal("10")
    assert opportunity.expected_net_profit == Decimal("7")
    assert opportunity.is_profitable_on_paper is True


def test_opportunity_can_be_unprofitable_after_costs():
    opportunity = _opportunity(
        sell_vwap=Decimal("101"),
        total_fees=Decimal("2"),
    )

    assert opportunity.expected_net_profit < Decimal("0")
    assert opportunity.is_profitable_on_paper is False


def test_opportunity_rejects_same_venue_on_both_legs():
    with pytest.raises(DomainValidationError):
        _opportunity(sell_venue_id="BINANCE")


def test_opportunity_rejects_executable_above_requested():
    with pytest.raises(DomainValidationError):
        _opportunity(executable_quantity=Decimal("2"))


def test_opportunity_payload_declares_safety_flags():
    payload = _opportunity().to_dict()

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False
    assert payload["is_executable"] is False


def test_limit_intent_requires_price():
    with pytest.raises(DomainValidationError):
        OrderIntent(
            venue_id="BINANCE",
            instrument_id="BTCUSDT",
            side=Side.BUY,
            order_type=OrderType.LIMIT,
            quantity=Decimal("1"),
        )


def test_intent_generates_idempotent_identifier():
    intent = OrderIntent(
        venue_id="BINANCE",
        instrument_id="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
    )

    assert intent.client_order_id.startswith("predarb-")
    assert intent.to_dict()["submitted"] is False


def _intent(identifier: str) -> OrderIntent:
    return OrderIntent(
        venue_id="BINANCE",
        instrument_id="BTCUSDT",
        side=Side.BUY,
        order_type=OrderType.MARKET,
        quantity=Decimal("1"),
        client_order_id=identifier,
    )


def test_plan_refuses_live_execution_mode():
    with pytest.raises(DomainValidationError):
        ExecutionPlan(
            opportunity_id="opp-1",
            legs=(_intent("a"),),
            execution_mode=ExecutionMode.LIVE,
        )


def test_plan_requires_at_least_one_leg():
    with pytest.raises(DomainValidationError):
        ExecutionPlan(
            opportunity_id="opp-1",
            legs=(),
        )


def test_plan_rejects_duplicated_client_order_id():
    with pytest.raises(DomainValidationError):
        ExecutionPlan(
            opportunity_id="opp-1",
            legs=(_intent("same"), _intent("same")),
        )


def test_plan_is_never_authorized_in_this_phase():
    plan = ExecutionPlan(
        opportunity_id="opp-1",
        legs=(_intent("a"), _intent("b")),
    )

    payload = plan.to_dict()

    assert plan.is_authorized is False
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert (
        payload["risk_decision"]["status"]
        == RiskStatus.BLOCKED.value
    )


def test_risk_decision_defaults_to_blocked():
    decision = RiskDecision()

    assert decision.approved is False
    assert decision.status is RiskStatus.BLOCKED


def test_risk_decision_rejects_inconsistent_approval():
    with pytest.raises(DomainValidationError):
        RiskDecision(
            approved=True,
            status=RiskStatus.BLOCKED,
        )

    with pytest.raises(DomainValidationError):
        RiskDecision(
            approved=False,
            status=RiskStatus.ELIGIBLE,
        )
