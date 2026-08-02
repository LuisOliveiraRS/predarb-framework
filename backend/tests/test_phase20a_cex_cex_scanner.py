"""Fase 20A - lucratividade liquida e scanner CEX-CEX."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.domain.enums import (
    RiskStatus,
    StrategyType,
)
from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    FeeUnknownError,
    PrecisionError,
)
from app.crypto_arbitrage.domain.fees import (
    FeeRate,
    FeeSchedule,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookLevel,
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.symbols import build_pair
from app.crypto_arbitrage.market_data.freshness import (
    FreshnessPolicy,
)
from app.crypto_arbitrage.opportunities.cex_cex import (
    CexCexScanner,
)
from app.crypto_arbitrage.opportunities.profitability import (
    CostModel,
    compute_breakdown,
    meets_thresholds,
    resolve_taker_rates,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)

PAIR = build_pair("BTC", "USDT")


def _book(venue, bid, ask, quantity="10", received=None):
    return OrderBookSnapshot(
        venue_id=venue,
        instrument_id="BTCUSDT",
        bids=(
            OrderBookLevel(
                price=Decimal(bid),
                quantity=Decimal(quantity),
            ),
        ),
        asks=(
            OrderBookLevel(
                price=Decimal(ask),
                quantity=Decimal(quantity),
            ),
        ),
        exchange_timestamp=received or MOMENT,
        received_timestamp=received or MOMENT,
    )


def _schedule(*venues, rate="0.001"):
    schedule = FeeSchedule()

    for venue in venues:
        schedule.register(
            FeeRate(
                venue_id=venue,
                instrument_id="BTCUSDT",
                maker_rate=Decimal(rate),
                taker_rate=Decimal(rate),
                source="test_fixture",
                effective_at=MOMENT
                - timedelta(days=1),
            )
        )

    return schedule


def _scanner(schedule=None, **cost_kwargs):
    return CexCexScanner(
        fee_schedule=schedule
        or _schedule("BINANCE", "OKX", "BYBIT"),
        cost_model=CostModel.create(**cost_kwargs),
        freshness=FreshnessPolicy.create(
            max_age_ms=1000
        ),
    )


# ---------------------------------------------------------------
# Lucratividade
# ---------------------------------------------------------------


def test_breakdown_discounts_every_cost():
    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="110",
        buy_fee_rate="0.001",
        sell_fee_rate="0.001",
        cost_model=CostModel.create(
            slippage_ratio="0",
            safety_buffer_ratio="0",
        ),
    )

    assert breakdown.gross_profit == Decimal("10")
    assert breakdown.buy_fee == Decimal("0.100")
    assert breakdown.sell_fee == Decimal("0.110")
    assert breakdown.expected_net_profit == Decimal("9.790")


def test_reserves_scale_with_notional_not_profit():
    """Reserva acompanha o tamanho da posicao, nao o do ganho."""

    small = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="101",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0.001",
            safety_buffer_ratio="0",
        ),
    )

    large = compute_breakdown(
        quantity="10",
        buy_vwap="100",
        sell_vwap="101",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0.001",
            safety_buffer_ratio="0",
        ),
    )

    assert large.slippage_reserve == (
        small.slippage_reserve * Decimal("10")
    )


def test_breakdown_computes_roi_over_capital_deployed():
    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="110",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0",
            safety_buffer_ratio="0",
        ),
    )

    assert breakdown.expected_roi == Decimal("0.1")


def test_costs_can_erase_an_apparent_edge():
    """Diferenca bruta positiva vira prejuizo apos custos."""

    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="100.1",
        buy_fee_rate="0.001",
        sell_fee_rate="0.001",
        cost_model=CostModel.create(),
    )

    assert breakdown.gross_profit > Decimal("0")
    assert breakdown.expected_net_profit < Decimal("0")
    assert breakdown.is_profitable is False


def test_breakdown_rejects_float():
    with pytest.raises(PrecisionError):
        compute_breakdown(
            quantity=1.0,
            buy_vwap="100",
            sell_vwap="110",
            buy_fee_rate="0",
            sell_fee_rate="0",
            cost_model=CostModel.create(),
        )


def test_thresholds_reject_non_positive_profit():
    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="100",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0",
            safety_buffer_ratio="0",
        ),
    )

    approved, reason = meets_thresholds(
        breakdown,
        CostModel.create(),
    )

    assert approved is False
    assert "não é positivo" in reason


def test_thresholds_enforce_minimum_profit():
    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="101",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0",
            safety_buffer_ratio="0",
        ),
    )

    approved, reason = meets_thresholds(
        breakdown,
        CostModel.create(minimum_net_profit="50"),
    )

    assert approved is False
    assert "abaixo do mínimo" in reason


def test_thresholds_enforce_minimum_roi():
    breakdown = compute_breakdown(
        quantity="1",
        buy_vwap="100",
        sell_vwap="101",
        buy_fee_rate="0",
        sell_fee_rate="0",
        cost_model=CostModel.create(
            slippage_ratio="0",
            safety_buffer_ratio="0",
        ),
    )

    approved, reason = meets_thresholds(
        breakdown,
        CostModel.create(minimum_roi="0.5"),
    )

    assert approved is False
    assert "ROI" in reason


def test_cost_model_rejects_ratio_above_one():
    with pytest.raises(DomainValidationError):
        CostModel.create(slippage_ratio="1.5")


def test_resolve_rates_fails_closed_on_unknown_fee():
    schedule = _schedule("BINANCE")

    with pytest.raises(FeeUnknownError):
        resolve_taker_rates(
            schedule,
            buy_venue_id="BINANCE",
            buy_instrument_id="BTCUSDT",
            sell_venue_id="OKX",
            sell_instrument_id="BTCUSDT",
            moment=MOMENT,
        )


# ---------------------------------------------------------------
# Scanner
# ---------------------------------------------------------------


def test_scanner_finds_directional_opportunity():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    assert report.best is not None

    best = report.best.opportunity

    assert best.buy_venue_id == "BINANCE"
    assert best.sell_venue_id == "OKX"
    assert best.strategy_type is (
        StrategyType.CEX_CEX_SPATIAL
    )


def test_scanner_evaluates_both_directions():
    """Comprar em A e vender em B nao e o mesmo que o inverso."""

    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    routes = {
        (
            item.buy_venue_id,
            item.sell_venue_id,
        )
        for item in report.rejected
    }

    assert ("OKX", "BINANCE") in routes


def test_scanner_ranks_by_expected_net_profit():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.1"),
            "OKX": _book("OKX", "110", "110.1"),
            "BYBIT": _book("BYBIT", "105", "105.1"),
        },
        now=MOMENT,
    )

    profits = [
        item.expected_net_profit
        for item in report.opportunities
    ]

    assert profits == sorted(profits, reverse=True)
    assert report.best.opportunity.sell_venue_id == "OKX"


def test_scanner_blocks_stale_book_before_computing():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book(
                "OKX",
                "105",
                "105.5",
                received=MOMENT - timedelta(seconds=30),
            ),
        },
        now=MOMENT,
    )

    assert report.opportunities == ()

    stale = [
        item
        for item in report.rejected
        if item.stage == "freshness"
    ]

    assert len(stale) == 1
    assert stale[0].buy_venue_id == "OKX"


def test_scanner_reports_insufficient_depth():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="100",
        books={
            "BINANCE": _book(
                "BINANCE",
                "100",
                "100.5",
                quantity="1",
            ),
            "OKX": _book(
                "OKX",
                "105",
                "105.5",
                quantity="1",
            ),
        },
        now=MOMENT,
    )

    assert report.opportunities == ()
    assert all(
        item.stage == "depth"
        for item in report.rejected
    )


def test_scanner_fails_closed_on_unknown_fee():
    """Invariante 15: taxa desconhecida invalida a oportunidade."""

    scanner = _scanner(schedule=_schedule("BINANCE"))

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    assert report.opportunities == ()
    assert any(
        item.stage == "fees" for item in report.rejected
    )


def test_scanner_rejects_when_costs_erase_the_edge():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.05"),
            "OKX": _book("OKX", "100.1", "100.2"),
        },
        now=MOMENT,
    )

    assert report.opportunities == ()
    assert any(
        item.stage == "profitability"
        for item in report.rejected
    )


def test_scanner_honours_minimum_profit():
    scanner = _scanner(minimum_net_profit="1000")

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    assert report.opportunities == ()


def test_scanner_requires_positive_quantity():
    scanner = _scanner()

    with pytest.raises(DomainValidationError):
        scanner.scan(
            pair=PAIR,
            quantity="0",
            books={},
            now=MOMENT,
        )


def test_scanner_requires_aware_now():
    scanner = _scanner()

    with pytest.raises(DomainValidationError):
        scanner.scan(
            pair=PAIR,
            quantity="1",
            books={},
            now=datetime(2026, 8, 2),
        )


def test_single_venue_produces_no_route():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5")
        },
        now=MOMENT,
    )

    assert report.opportunities == ()
    assert report.rejected == ()


def test_opportunity_stays_blocked_and_not_executable():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    best = report.best.opportunity

    assert best.risk_status is RiskStatus.BLOCKED
    assert best.is_executable is False


def test_report_payload_declares_safety_flags():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    payload = report.to_dict()

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True
    assert payload["execution_authorized"] is False
    assert payload["financial_execution"] is False
    assert payload["order_submission_available"] is False
    assert (
        payload["automatic_execution_authorized"] is False
    )


def test_report_carries_breakdown_for_audit():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book("BINANCE", "100", "100.5"),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    breakdown = report.to_dict()["opportunities"][0][
        "breakdown"
    ]

    for key in (
        "buy_vwap",
        "sell_vwap",
        "buy_fee",
        "sell_fee",
        "slippage_reserve",
        "safety_buffer",
        "expected_net_profit",
        "expected_roi",
    ):
        assert key in breakdown


def test_vwap_is_used_instead_of_top_of_book():
    """Consumir profundidade piora o preco, e isso deve aparecer."""

    deep = OrderBookSnapshot(
        venue_id="BINANCE",
        instrument_id="BTCUSDT",
        bids=(
            OrderBookLevel(
                price=Decimal("99"),
                quantity=Decimal("1"),
            ),
        ),
        asks=(
            OrderBookLevel(
                price=Decimal("100"),
                quantity=Decimal("1"),
            ),
            OrderBookLevel(
                price=Decimal("200"),
                quantity=Decimal("1"),
            ),
        ),
        exchange_timestamp=MOMENT,
        received_timestamp=MOMENT,
    )

    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="2",
        books={
            "BINANCE": deep,
            "OKX": _book("OKX", "300", "301"),
        },
        now=MOMENT,
    )

    best = report.best

    # Topo de livro seria 100. O VWAP de 2 unidades e 150.
    assert best.breakdown.buy_vwap == Decimal("150")


def test_scanner_records_data_age():
    scanner = _scanner()

    report = scanner.scan(
        pair=PAIR,
        quantity="1",
        books={
            "BINANCE": _book(
                "BINANCE",
                "100",
                "100.5",
                received=MOMENT
                - timedelta(milliseconds=120),
            ),
            "OKX": _book("OKX", "105", "105.5"),
        },
        now=MOMENT,
    )

    assert report.best.opportunity.data_age_ms == Decimal(
        "120"
    )


def test_scanner_status_declares_read_only():
    status = _scanner().status()

    assert status["read_only"] is True
    assert status["execution_authorized"] is False
    assert status["order_submission_available"] is False
