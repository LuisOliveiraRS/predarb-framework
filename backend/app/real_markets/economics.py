from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Mapping

from app.real_markets.matching import (
    ManualMarketMatchStore,
    canonical_outcome_label,
)
from app.real_markets.models import (
    MarketQuote,
    MarketSnapshot,
)
from app.real_markets.service import (
    RealMarketDataService,
    real_market_data_service,
)


MONEY_QUANTUM = Decimal("0.00000001")
RATE_QUANTUM = Decimal("0.0000000001")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decimal(
    value: Any,
    default: Decimal = Decimal("0"),
) -> Decimal:
    if value is None or isinstance(value, bool):
        return default

    try:
        return Decimal(str(value))
    except Exception:
        return default


def _env_decimal(
    name: str,
    default: str,
) -> Decimal:
    value = os.getenv(name)

    if value is None:
        value = default

    return _decimal(
        value,
        _decimal(default),
    )


def _env_int(
    name: str,
    default: int,
) -> int:
    value = os.getenv(name)

    if value is None:
        return int(default)

    try:
        return int(value)
    except ValueError:
        return int(default)


def _env_json_mapping(
    name: str,
    default: Mapping[str, Any],
) -> dict[str, Any]:
    raw = os.getenv(name)

    if raw is None:
        return dict(default)

    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        return dict(default)

    if not isinstance(parsed, Mapping):
        return dict(default)

    return {
        str(key): value
        for key, value in parsed.items()
    }


def _parse_datetime(
    value: str | None,
) -> datetime | None:
    if not value:
        return None

    normalized = value.strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


def _rounded(
    value: Decimal,
    quantum: Decimal = MONEY_QUANTUM,
) -> float:
    return float(
        value.quantize(
            quantum,
            rounding=ROUND_HALF_UP,
        )
    )


def _split_market_key(
    key: str,
) -> tuple[str, str]:
    connector_id, separator, market_id = (
        key.partition(":")
    )

    if (
        not separator
        or not connector_id
        or not market_id
    ):
        raise ValueError(
            f"Chave de mercado inválida: {key}"
        )

    return connector_id, market_id


@dataclass(frozen=True)
class EconomicModelConfiguration:
    max_snapshot_age_seconds: int
    max_simulated_quantity: Decimal
    min_net_edge: Decimal
    min_net_profit: Decimal
    fee_rates: dict[str, Decimal]
    slippage_bps: dict[str, Decimal]
    currency_groups: dict[str, str]

    @classmethod
    def from_env(
        cls,
    ) -> "EconomicModelConfiguration":
        fee_rates_raw = _env_json_mapping(
            "REAL_MARKET_ECONOMIC_FEE_RATES_JSON",
            {
                "default": 0.0,
                "mock-real-market": 0.0,
                "polymarket": 0.0,
            },
        )

        slippage_raw = _env_json_mapping(
            "REAL_MARKET_ECONOMIC_SLIPPAGE_BPS_JSON",
            {
                "default": 10.0,
                "mock-real-market": 0.0,
                "polymarket": 10.0,
            },
        )

        currency_groups_raw = _env_json_mapping(
            "REAL_MARKET_ECONOMIC_CURRENCY_GROUPS_JSON",
            {
                "USD": "USD_STABLE",
                "USDC": "USD_STABLE",
                "USDT": "USD_STABLE",
                "PUSD": "USD_STABLE",
            },
        )

        fee_rates = {
            str(key): max(
                Decimal("0"),
                min(
                    Decimal("1"),
                    _decimal(value),
                ),
            )
            for key, value in fee_rates_raw.items()
        }

        slippage_bps = {
            str(key): max(
                Decimal("0"),
                min(
                    Decimal("10000"),
                    _decimal(value),
                ),
            )
            for key, value in slippage_raw.items()
        }

        currency_groups = {
            str(key).upper(): str(value)
            for key, value in (
                currency_groups_raw.items()
            )
        }

        return cls(
            max_snapshot_age_seconds=max(
                1,
                min(
                    _env_int(
                        "REAL_MARKET_ECONOMIC_MAX_SNAPSHOT_AGE_SECONDS",
                        90,
                    ),
                    86400,
                ),
            ),
            max_simulated_quantity=max(
                Decimal("0"),
                _env_decimal(
                    "REAL_MARKET_ECONOMIC_MAX_SIMULATED_QUANTITY",
                    "1000",
                ),
            ),
            min_net_edge=max(
                Decimal("0"),
                min(
                    Decimal("1"),
                    _env_decimal(
                        "REAL_MARKET_ECONOMIC_MIN_NET_EDGE",
                        "0.0025",
                    ),
                ),
            ),
            min_net_profit=max(
                Decimal("0"),
                _env_decimal(
                    "REAL_MARKET_ECONOMIC_MIN_NET_PROFIT",
                    "0.01",
                ),
            ),
            fee_rates=fee_rates,
            slippage_bps=slippage_bps,
            currency_groups=currency_groups,
        )

    def fee_rate(
        self,
        connector_id: str,
    ) -> Decimal:
        return self.fee_rates.get(
            connector_id,
            self.fee_rates.get(
                "default",
                Decimal("0"),
            ),
        )

    def slippage_rate(
        self,
        connector_id: str,
    ) -> Decimal:
        bps = self.slippage_bps.get(
            connector_id,
            self.slippage_bps.get(
                "default",
                Decimal("0"),
            ),
        )

        return bps / Decimal("10000")

    def currency_group(
        self,
        currency: str,
    ) -> str:
        normalized = currency.strip().upper()

        return self.currency_groups.get(
            normalized,
            normalized,
        )

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return {
            "max_snapshot_age_seconds": (
                self.max_snapshot_age_seconds
            ),
            "max_simulated_quantity": _rounded(
                self.max_simulated_quantity
            ),
            "min_net_edge": _rounded(
                self.min_net_edge,
                RATE_QUANTUM,
            ),
            "min_net_profit": _rounded(
                self.min_net_profit
            ),
            "fee_rates": {
                key: _rounded(
                    value,
                    RATE_QUANTUM,
                )
                for key, value in (
                    self.fee_rates.items()
                )
            },
            "slippage_bps": {
                key: _rounded(
                    value,
                    RATE_QUANTUM,
                )
                for key, value in (
                    self.slippage_bps.items()
                )
            },
            "currency_groups": dict(
                self.currency_groups
            ),
        }


@dataclass(frozen=True)
class EconomicLeg:
    connector_id: str
    market_id: str
    outcome_id: str
    outcome_label: str
    canonical_outcome: str
    ask: float | None
    ask_size: float | None
    fee_rate: float
    slippage_bps: float

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class EconomicOpportunityEngine:
    """Avaliação econômica simulada de pares confirmados."""

    SUPPORTED_COMPLEMENTARY_PAIRS = (
        ("YES", "NO"),
        ("NO", "YES"),
    )

    def __init__(
        self,
        *,
        market_data_service: (
            RealMarketDataService
        ) = real_market_data_service,
        match_store: (
            ManualMarketMatchStore
            | None
        ) = None,
        configuration: (
            EconomicModelConfiguration
            | None
        ) = None,
    ) -> None:
        self.market_data_service = (
            market_data_service
        )

        self.match_store = (
            match_store
            if match_store is not None
            else ManualMarketMatchStore()
        )

        self.configuration = (
            configuration
            if configuration is not None
            else (
                EconomicModelConfiguration
                .from_env()
            )
        )

    @staticmethod
    def _safe_flags() -> dict[str, Any]:
        return {
            "economic_analysis_only": True,
            "shadow_only": True,
            "market_data_only": True,
            "read_only_market_access": True,
            "order_submission_available": False,
            "automatic_execution_authorized": False,
            "paper_execution_authorized": False,
            "live_authorization": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "next_step_authorized": False,
        }

    @staticmethod
    def _snapshot_age_seconds(
        snapshot: MarketSnapshot,
    ) -> float | None:
        captured_at = _parse_datetime(
            snapshot.captured_at
        )

        if captured_at is None:
            return None

        age = (
            datetime.now(timezone.utc)
            - captured_at
        ).total_seconds()

        return round(
            max(0.0, age),
            6,
        )

    @staticmethod
    def _canonical_quotes(
        snapshot: MarketSnapshot,
    ) -> dict[
        str,
        tuple[
            Any,
            MarketQuote,
        ],
    ]:
        quote_by_outcome_id = {
            quote.outcome_id: quote
            for quote in snapshot.quotes
        }

        canonical: dict[
            str,
            tuple[
                Any,
                MarketQuote,
            ],
        ] = {}

        for outcome in (
            snapshot.market.outcomes
        ):
            quote = quote_by_outcome_id.get(
                outcome.outcome_id
            )

            if quote is None:
                continue

            label = canonical_outcome_label(
                outcome.label
            )

            if label in canonical:
                raise ValueError(
                    "Outcomes duplicados após "
                    "normalização canônica."
                )

            canonical[label] = (
                outcome,
                quote,
            )

        return canonical

    def _leg(
        self,
        *,
        snapshot: MarketSnapshot,
        canonical_outcome: str,
    ) -> EconomicLeg:
        canonical = self._canonical_quotes(
            snapshot
        )

        item = canonical.get(
            canonical_outcome
        )

        if item is None:
            raise ValueError(
                "Outcome canônico ausente: "
                f"{canonical_outcome}"
            )

        outcome, quote = item

        return EconomicLeg(
            connector_id=(
                snapshot.market.connector_id
            ),
            market_id=(
                snapshot.market.market_id
            ),
            outcome_id=(
                outcome.outcome_id
            ),
            outcome_label=outcome.label,
            canonical_outcome=(
                canonical_outcome
            ),
            ask=quote.ask,
            ask_size=quote.ask_size,
            fee_rate=_rounded(
                self.configuration.fee_rate(
                    snapshot.market.connector_id
                ),
                RATE_QUANTUM,
            ),
            slippage_bps=_rounded(
                self.configuration.slippage_bps.get(
                    snapshot.market.connector_id,
                    self.configuration.slippage_bps.get(
                        "default",
                        Decimal("0"),
                    ),
                ),
                RATE_QUANTUM,
            ),
        )

    def _evaluate_direction(
        self,
        *,
        left_snapshot: MarketSnapshot,
        right_snapshot: MarketSnapshot,
        left_outcome: str,
        right_outcome: str,
    ) -> dict[str, Any]:
        try:
            left_leg = self._leg(
                snapshot=left_snapshot,
                canonical_outcome=(
                    left_outcome
                ),
            )

            right_leg = self._leg(
                snapshot=right_snapshot,
                canonical_outcome=(
                    right_outcome
                ),
            )

        except ValueError as exc:
            return {
                "status": "REJECTED",
                "direction": (
                    f"{left_outcome}_LEFT__"
                    f"{right_outcome}_RIGHT"
                ),
                "reason_codes": [
                    "OUTCOME_MAPPING_ERROR"
                ],
                "message": str(exc),
            }

        reason_codes: list[str] = []

        if left_leg.ask is None:
            reason_codes.append(
                "LEFT_ASK_MISSING"
            )

        if right_leg.ask is None:
            reason_codes.append(
                "RIGHT_ASK_MISSING"
            )

        if left_leg.ask_size is None:
            reason_codes.append(
                "LEFT_ASK_SIZE_MISSING"
            )

        if right_leg.ask_size is None:
            reason_codes.append(
                "RIGHT_ASK_SIZE_MISSING"
            )

        if (
            left_leg.ask_size is not None
            and left_leg.ask_size <= 0
        ):
            reason_codes.append(
                "LEFT_LIQUIDITY_EMPTY"
            )

        if (
            right_leg.ask_size is not None
            and right_leg.ask_size <= 0
        ):
            reason_codes.append(
                "RIGHT_LIQUIDITY_EMPTY"
            )

        if reason_codes:
            return {
                "status": "REJECTED",
                "direction": (
                    f"{left_outcome}_LEFT__"
                    f"{right_outcome}_RIGHT"
                ),
                "reason_codes": reason_codes,
                "legs": [
                    left_leg.to_dict(),
                    right_leg.to_dict(),
                ],
            }

        left_ask = _decimal(
            left_leg.ask
        )

        right_ask = _decimal(
            right_leg.ask
        )

        left_size = _decimal(
            left_leg.ask_size
        )

        right_size = _decimal(
            right_leg.ask_size
        )

        quantity = min(
            left_size,
            right_size,
            self.configuration.max_simulated_quantity,
        )

        if quantity <= 0:
            return {
                "status": "REJECTED",
                "direction": (
                    f"{left_outcome}_LEFT__"
                    f"{right_outcome}_RIGHT"
                ),
                "reason_codes": [
                    "NO_EXECUTABLE_LIQUIDITY"
                ],
                "legs": [
                    left_leg.to_dict(),
                    right_leg.to_dict(),
                ],
            }

        left_fee_rate = (
            self.configuration.fee_rate(
                left_leg.connector_id
            )
        )

        right_fee_rate = (
            self.configuration.fee_rate(
                right_leg.connector_id
            )
        )

        left_slippage_rate = (
            self.configuration.slippage_rate(
                left_leg.connector_id
            )
        )

        right_slippage_rate = (
            self.configuration.slippage_rate(
                right_leg.connector_id
            )
        )

        left_raw_cost = (
            left_ask * quantity
        )

        right_raw_cost = (
            right_ask * quantity
        )

        raw_cost = (
            left_raw_cost
            + right_raw_cost
        )

        left_fee = (
            left_raw_cost
            * left_fee_rate
        )

        right_fee = (
            right_raw_cost
            * right_fee_rate
        )

        fee_cost = (
            left_fee
            + right_fee
        )

        left_slippage = (
            left_raw_cost
            * left_slippage_rate
        )

        right_slippage = (
            right_raw_cost
            * right_slippage_rate
        )

        slippage_cost = (
            left_slippage
            + right_slippage
        )

        total_cost = (
            raw_cost
            + fee_cost
            + slippage_cost
        )

        payout = quantity

        gross_profit = (
            payout
            - raw_cost
        )

        net_profit = (
            payout
            - total_cost
        )

        gross_edge = (
            gross_profit / payout
        )

        net_edge = (
            net_profit / payout
        )

        status = (
            "PROFITABLE"
            if (
                net_edge
                >= self.configuration.min_net_edge
                and net_profit
                >= self.configuration.min_net_profit
            )
            else "NOT_PROFITABLE"
        )

        return {
            "status": status,
            "direction": (
                f"{left_outcome}_LEFT__"
                f"{right_outcome}_RIGHT"
            ),
            "reason_codes": (
                []
                if status == "PROFITABLE"
                else [
                    "NET_RETURN_BELOW_THRESHOLD"
                ]
            ),
            "legs": [
                left_leg.to_dict(),
                right_leg.to_dict(),
            ],
            "simulated_quantity": _rounded(
                quantity
            ),
            "raw_cost": _rounded(
                raw_cost
            ),
            "fee_cost": _rounded(
                fee_cost
            ),
            "slippage_cost": _rounded(
                slippage_cost
            ),
            "total_cost": _rounded(
                total_cost
            ),
            "simulated_payout": _rounded(
                payout
            ),
            "gross_profit": _rounded(
                gross_profit
            ),
            "net_profit": _rounded(
                net_profit
            ),
            "gross_edge": _rounded(
                gross_edge,
                RATE_QUANTUM,
            ),
            "net_edge": _rounded(
                net_edge,
                RATE_QUANTUM,
            ),
        }

    async def evaluate_pair(
        self,
        *,
        left_key: str,
        right_key: str,
        source: str,
        match_id: str | None = None,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        (
            left_connector_id,
            left_market_id,
        ) = _split_market_key(
            left_key
        )

        (
            right_connector_id,
            right_market_id,
        ) = _split_market_key(
            right_key
        )

        if (
            left_connector_id
            == right_connector_id
        ):
            raise ValueError(
                "A avaliação econômica exige "
                "conectores diferentes."
            )

        (
            left_snapshot,
            right_snapshot,
        ) = await asyncio.gather(
            self.market_data_service.get_snapshot(
                connector_id=(
                    left_connector_id
                ),
                market_id=(
                    left_market_id
                ),
                force_refresh=force_refresh,
            ),
            self.market_data_service.get_snapshot(
                connector_id=(
                    right_connector_id
                ),
                market_id=(
                    right_market_id
                ),
                force_refresh=force_refresh,
            ),
        )

        left_age = self._snapshot_age_seconds(
            left_snapshot
        )

        right_age = self._snapshot_age_seconds(
            right_snapshot
        )

        reason_codes: list[str] = []

        if left_age is None:
            reason_codes.append(
                "LEFT_CAPTURE_TIME_INVALID"
            )
        elif (
            left_age
            > self.configuration.max_snapshot_age_seconds
        ):
            reason_codes.append(
                "LEFT_SNAPSHOT_STALE"
            )

        if right_age is None:
            reason_codes.append(
                "RIGHT_CAPTURE_TIME_INVALID"
            )
        elif (
            right_age
            > self.configuration.max_snapshot_age_seconds
        ):
            reason_codes.append(
                "RIGHT_SNAPSHOT_STALE"
            )

        left_group = (
            self.configuration.currency_group(
                left_snapshot.market.currency
            )
        )

        right_group = (
            self.configuration.currency_group(
                right_snapshot.market.currency
            )
        )

        if left_group != right_group:
            reason_codes.append(
                "CURRENCY_GROUP_MISMATCH"
            )

        base_payload = {
            "match_id": match_id,
            "source": source,
            "manual_match_confirmed": (
                source
                == "MANUAL_CONFIRMED_MATCH"
            ),
            "left_key": left_key,
            "right_key": right_key,
            "evaluated_at": _utc_now(),
            "left_snapshot_age_seconds": (
                left_age
            ),
            "right_snapshot_age_seconds": (
                right_age
            ),
            "left_currency": (
                left_snapshot.market.currency
            ),
            "right_currency": (
                right_snapshot.market.currency
            ),
            "currency_group": (
                left_group
                if left_group == right_group
                else None
            ),
            "configuration": (
                self.configuration.to_dict()
            ),
        }

        if reason_codes:
            return {
                **base_payload,
                "status": "REJECTED",
                "reason_codes": reason_codes,
                "directions": [],
                "best_direction": None,
                **self._safe_flags(),
            }

        directions = [
            self._evaluate_direction(
                left_snapshot=left_snapshot,
                right_snapshot=right_snapshot,
                left_outcome=left_outcome,
                right_outcome=right_outcome,
            )
            for (
                left_outcome,
                right_outcome,
            ) in (
                self.SUPPORTED_COMPLEMENTARY_PAIRS
            )
        ]

        valid_directions = [
            item
            for item in directions
            if (
                item.get("status")
                != "REJECTED"
            )
        ]

        best_direction = (
            max(
                valid_directions,
                key=lambda item: (
                    item.get(
                        "net_profit",
                        float("-inf"),
                    )
                ),
            )
            if valid_directions
            else None
        )

        if any(
            item.get("status")
            == "PROFITABLE"
            for item in directions
        ):
            status = "PROFITABLE"

        elif valid_directions:
            status = "NOT_PROFITABLE"

        else:
            status = "REJECTED"

        return {
            **base_payload,
            "status": status,
            "reason_codes": (
                []
                if status != "REJECTED"
                else [
                    "NO_VALID_BINARY_DIRECTION"
                ]
            ),
            "directions": directions,
            "best_direction": (
                best_direction
            ),
            **self._safe_flags(),
        }

    async def evaluate_match(
        self,
        *,
        match_id: str,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        record = next(
            (
                item
                for item in (
                    self.match_store
                    .list_matches()
                )
                if item.get("id")
                == match_id
            ),
            None,
        )

        if record is None:
            raise KeyError(
                "Correspondência manual "
                f"não encontrada: {match_id}"
            )

        return await self.evaluate_pair(
            left_key=str(
                record["left_key"]
            ),
            right_key=str(
                record["right_key"]
            ),
            source=(
                "MANUAL_CONFIRMED_MATCH"
            ),
            match_id=match_id,
            force_refresh=force_refresh,
        )

    async def evaluate_confirmed_matches(
        self,
        *,
        force_refresh: bool = False,
    ) -> dict[str, Any]:
        matches = (
            self.match_store
            .list_matches()
        )

        if not matches:
            return {
                "status": "NO_CONFIRMED_MATCHES",
                "evaluated_at": _utc_now(),
                "confirmed_matches": 0,
                "profitable": 0,
                "not_profitable": 0,
                "rejected": 0,
                "opportunities": [],
                "configuration": (
                    self.configuration.to_dict()
                ),
                **self._safe_flags(),
            }

        results = await asyncio.gather(
            *[
                self.evaluate_pair(
                    left_key=str(
                        record["left_key"]
                    ),
                    right_key=str(
                        record["right_key"]
                    ),
                    source=(
                        "MANUAL_CONFIRMED_MATCH"
                    ),
                    match_id=str(
                        record["id"]
                    ),
                    force_refresh=(
                        force_refresh
                    ),
                )
                for record in matches
            ],
            return_exceptions=True,
        )

        opportunities: list[
            dict[str, Any]
        ] = []

        for record, result in zip(
            matches,
            results,
            strict=True,
        ):
            if isinstance(
                result,
                Exception,
            ):
                opportunities.append(
                    {
                        "match_id": (
                            record.get("id")
                        ),
                        "left_key": (
                            record.get(
                                "left_key"
                            )
                        ),
                        "right_key": (
                            record.get(
                                "right_key"
                            )
                        ),
                        "status": "ERROR",
                        "error": str(result),
                        **self._safe_flags(),
                    }
                )
            else:
                opportunities.append(
                    result
                )

        opportunities.sort(
            key=lambda item: (
                (
                    item.get(
                        "best_direction"
                    )
                    or {}
                ).get(
                    "net_profit",
                    float("-inf"),
                )
            ),
            reverse=True,
        )

        return {
            "status": "EVALUATED",
            "evaluated_at": _utc_now(),
            "confirmed_matches": len(
                matches
            ),
            "profitable": sum(
                1
                for item in opportunities
                if item.get("status")
                == "PROFITABLE"
            ),
            "not_profitable": sum(
                1
                for item in opportunities
                if item.get("status")
                == "NOT_PROFITABLE"
            ),
            "rejected": sum(
                1
                for item in opportunities
                if item.get("status")
                in {
                    "REJECTED",
                    "ERROR",
                }
            ),
            "opportunities": (
                opportunities
            ),
            "configuration": (
                self.configuration.to_dict()
            ),
            **self._safe_flags(),
        }

    def health(
        self,
    ) -> dict[str, Any]:
        matches = (
            self.match_store
            .list_matches()
        )

        return {
            "status": "healthy",
            "confirmed_matches": len(
                matches
            ),
            "supported_structure": (
                "BINARY_YES_NO"
            ),
            "configuration": (
                self.configuration.to_dict()
            ),
            "manual_match_required": True,
            "automatic_execution_authorized": False,
            **self._safe_flags(),
        }


economic_opportunity_engine = (
    EconomicOpportunityEngine()
)
