"""Fase 18 - aritmetica Decimal, simbolos e taxas."""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

import pytest

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    FeeUnknownError,
    PrecisionError,
    SymbolNormalizationError,
)
from app.crypto_arbitrage.domain.fees import (
    FeeRate,
    FeeSchedule,
    apply_fee,
)
from app.crypto_arbitrage.domain.money import (
    ensure_non_negative,
    ensure_positive,
    ensure_rate,
    quantize_down,
    quantize_up,
    to_decimal,
)
from app.crypto_arbitrage.domain.symbols import (
    build_pair,
    normalize_asset,
    parse_symbol,
)


MOMENT = datetime(
    2026,
    8,
    2,
    tzinfo=timezone.utc,
)


def test_float_is_rejected_instead_of_converted():
    with pytest.raises(PrecisionError):
        to_decimal(0.1, field_name="price")


def test_bool_is_rejected():
    with pytest.raises(DomainValidationError):
        to_decimal(True, field_name="price")


def test_accepts_decimal_int_and_str():
    assert to_decimal(Decimal("1.5")) == Decimal("1.5")
    assert to_decimal(7) == Decimal("7")
    assert to_decimal(" 2.25 ") == Decimal("2.25")


def test_rejects_non_finite_and_garbage():
    with pytest.raises(DomainValidationError):
        to_decimal("NaN")

    with pytest.raises(DomainValidationError):
        to_decimal("Infinity")

    with pytest.raises(DomainValidationError):
        to_decimal("abc")


def test_positive_and_non_negative_guards():
    assert ensure_positive("1") == Decimal("1")
    assert ensure_non_negative("0") == Decimal("0")

    with pytest.raises(DomainValidationError):
        ensure_positive("0")

    with pytest.raises(DomainValidationError):
        ensure_non_negative("-1")


def test_rate_must_be_a_fraction():
    assert ensure_rate("0.001") == Decimal("0.001")

    with pytest.raises(DomainValidationError):
        ensure_rate("1.5")


def test_quantize_down_is_conservative():
    assert quantize_down(
        "1.23456789",
        "0.001",
    ) == Decimal("1.234")


def test_quantize_up_is_conservative_for_costs():
    assert quantize_up(
        "1.2341",
        "0.001",
    ) == Decimal("1.235")


def test_quantize_requires_positive_step():
    with pytest.raises(DomainValidationError):
        quantize_down("1", "0")


def test_normalize_asset_applies_aliases():
    assert normalize_asset("xbt") == "BTC"
    assert normalize_asset(" eth ") == "ETH"
    assert normalize_asset("ZUSD") == "USD"


def test_normalize_asset_rejects_empty_and_invalid():
    with pytest.raises(SymbolNormalizationError):
        normalize_asset("")

    with pytest.raises(SymbolNormalizationError):
        normalize_asset("BT C")


def test_parse_symbol_with_separators():
    for raw in ("BTC/USDT", "BTC-USDT", "BTC_USDT"):
        pair = parse_symbol(raw)

        assert pair.base_asset == "BTC"
        assert pair.quote_asset == "USDT"
        assert pair.canonical == "BTC/USDT"


def test_parse_symbol_concatenated_prefers_longest_quote():
    pair = parse_symbol("BTCUSDT")

    assert pair.base_asset == "BTC"
    assert pair.quote_asset == "USDT"


def test_parse_symbol_normalizes_venue_specific_alias():
    pair = parse_symbol("XBT/USD")

    assert pair.canonical == "BTC/USD"


def test_parse_symbol_refuses_to_guess():
    with pytest.raises(SymbolNormalizationError):
        parse_symbol("ABCDEF")


def test_pair_rejects_identical_assets():
    with pytest.raises(SymbolNormalizationError):
        build_pair("BTC", "BTC")


def _fee(**overrides):
    payload = {
        "venue_id": "BINANCE",
        "instrument_id": "BTCUSDT",
        "maker_rate": Decimal("0.001"),
        "taker_rate": Decimal("0.001"),
        "source": "account_query",
        "effective_at": MOMENT,
    }

    payload.update(overrides)

    return FeeRate(**payload)


def test_fee_requires_traceable_source():
    with pytest.raises(DomainValidationError):
        _fee(source="  ")


def test_fee_requires_aware_timestamps():
    with pytest.raises(DomainValidationError):
        _fee(effective_at=datetime(2026, 8, 2))


def test_unknown_fee_blocks_instead_of_defaulting():
    schedule = FeeSchedule()

    with pytest.raises(FeeUnknownError):
        schedule.get("BINANCE", "BTCUSDT")


def test_known_fee_is_returned():
    schedule = FeeSchedule()
    schedule.register(_fee())

    rate = schedule.taker_rate(
        "binance",
        "btcusdt",
        moment=MOMENT,
    )

    assert rate == Decimal("0.001")


def test_expired_fee_is_treated_as_unknown():
    schedule = FeeSchedule()

    schedule.register(
        _fee(expires_at=MOMENT + timedelta(hours=1))
    )

    with pytest.raises(FeeUnknownError):
        schedule.get(
            "BINANCE",
            "BTCUSDT",
            moment=MOMENT + timedelta(hours=2),
        )


def test_fee_rejects_inverted_validity_window():
    with pytest.raises(DomainValidationError):
        _fee(expires_at=MOMENT - timedelta(hours=1))


def test_apply_fee_uses_decimal():
    assert apply_fee(
        Decimal("1000"),
        Decimal("0.001"),
    ) == Decimal("1.000")
