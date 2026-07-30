from __future__ import annotations

import asyncio
import os
import time
from collections.abc import Mapping, Sequence
from typing import Any
from urllib.parse import quote, urlparse

import httpx

from app.real_markets.connectors import ReadOnlyMarketConnector
from app.real_markets.models import (
    ConnectorHealth,
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
    utc_now,
)


OFFICIAL_BASE_URL = (
    "https://external-api.kalshi.com/trade-api/v2"
)


def _env_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)

    if value is None:
        return default

    return value.strip().lower() in {
        "1", "true", "yes", "on",
    }


def _env_float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _validate_url(
    value: str,
    *,
    allow_insecure_http: bool,
) -> str:
    normalized = str(value or "").strip().rstrip("/")
    parsed = urlparse(normalized)

    allowed = {"https"}

    if allow_insecure_http:
        allowed.add("http")

    if parsed.scheme not in allowed or not parsed.netloc:
        raise ValueError("URL Kalshi inv?lida.")

    return normalized


def _number(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    if result < 0:
        return None

    if result > 1 and result <= 100:
        result /= 100

    if result > 1:
        return None

    return round(result, 10)


def _size(value: Any) -> float | None:
    try:
        result = float(value)
    except (TypeError, ValueError):
        return None

    return result if result >= 0 else None


def _best_bid(
    levels: Any,
) -> tuple[float | None, float | None]:
    if not isinstance(levels, Sequence):
        return None, None

    parsed: list[tuple[float, float | None]] = []

    for level in levels:
        if (
            not isinstance(level, Sequence)
            or isinstance(level, (str, bytes))
            or len(level) < 2
        ):
            continue

        price = _number(level[0])
        quantity = _size(level[1])

        if price is not None:
            parsed.append((price, quantity))

    if not parsed:
        return None, None

    return max(parsed, key=lambda item: item[0])


class KalshiReadOnlyConnector(ReadOnlyMarketConnector):
    connector_id = "kalshi"
    name = "Kalshi Public Market Data"
    kind = "prediction_market"
    read_only = True

    def __init__(
        self,
        *,
        base_url: str = OFFICIAL_BASE_URL,
        timeout_seconds: float = 12.0,
        max_retries: int = 2,
        default_market_limit: int = 100,
        transport: httpx.AsyncBaseTransport | None = None,
        allow_insecure_http: bool = False,
    ) -> None:
        self.base_url = _validate_url(
            base_url,
            allow_insecure_http=allow_insecure_http,
        )
        self.timeout_seconds = max(
            1.0,
            min(float(timeout_seconds), 60.0),
        )
        self.max_retries = max(
            0,
            min(int(max_retries), 5),
        )
        self.default_market_limit = max(
            1,
            min(int(default_market_limit), 1000),
        )
        self.transport = transport

    @property
    def capabilities(self) -> tuple[str, ...]:
        return (
            "market_data",
            "quotes",
            "snapshots",
            "public_rest_api",
            "public_orderbook",
        )

    async def _get(
        self,
        path: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(
                    base_url=self.base_url,
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                    follow_redirects=True,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": "PredArb-ReadOnly/1.0",
                    },
                ) as client:
                    response = await client.get(
                        path,
                        params=params,
                    )

                response.raise_for_status()
                return response.json()

            except Exception as exc:
                last_error = exc

                if attempt < self.max_retries:
                    await asyncio.sleep(
                        0.25 * (2 ** attempt)
                    )

        raise RuntimeError(
            f"Falha na API p?blica Kalshi: {last_error}"
        )

    @staticmethod
    def _normalize_market(
        raw: Mapping[str, Any],
    ) -> NormalizedMarket:
        ticker = str(
            raw.get("ticker") or ""
        ).strip()

        if not ticker:
            raise ValueError(
                "Mercado Kalshi sem ticker."
            )

        title_parts: list[str] = []

        for field in (
            "title",
            "subtitle",
            "yes_sub_title",
        ):
            value = str(
                raw.get(field) or ""
            ).strip()

            if value and value not in title_parts:
                title_parts.append(value)

        title = " ? ".join(title_parts) or ticker

        status = {
            "active": "OPEN",
            "open": "OPEN",
            "initialized": "UNKNOWN",
            "closed": "CLOSED",
            "settled": "RESOLVED",
            "finalized": "RESOLVED",
            "paused": "SUSPENDED",
            "unopened": "UNKNOWN",
        }.get(
            str(raw.get("status") or "").lower(),
            "UNKNOWN",
        )

        return NormalizedMarket(
            connector_id="kalshi",
            market_id=ticker,
            title=title,
            status=status,
            outcomes=(
                MarketOutcome(
                    outcome_id="YES",
                    label="Yes",
                    token_id=f"{ticker}:YES",
                ),
                MarketOutcome(
                    outcome_id="NO",
                    label="No",
                    token_id=f"{ticker}:NO",
                ),
            ),
            close_time=(
                raw.get("close_time")
                or raw.get(
                    "expected_expiration_time"
                )
                or raw.get("expiration_time")
            ),
            source_url=(
                f"{OFFICIAL_BASE_URL}/markets/{ticker}"
            ),
            description=(
                raw.get("rules_primary")
                or raw.get("subtitle")
            ),
            metadata={
                "event_ticker": raw.get("event_ticker"),
                "yes_sub_title": raw.get(
                    "yes_sub_title"
                ),
                "no_sub_title": raw.get(
                    "no_sub_title"
                ),
                "platform": "kalshi",
                "read_only": True,
                "authentication_required": False,
                "trading_endpoints_enabled": False,
            },
        )

    async def health(self) -> ConnectorHealth:
        started = time.perf_counter()

        try:
            payload = await self._get(
                "/markets",
                params={
                    "status": "open",
                    "limit": 1,
                    "mve_filter": "exclude",
                },
            )

            healthy = (
                isinstance(payload, Mapping)
                and isinstance(
                    payload.get("markets"),
                    list,
                )
            )

            return ConnectorHealth(
                connector_id=self.connector_id,
                name=self.name,
                healthy=healthy,
                message=(
                    "API p?blica Kalshi dispon?vel."
                    if healthy
                    else "Resposta Kalshi inv?lida."
                ),
                capabilities=self.capabilities,
                metadata={
                    "latency_ms": round(
                        (
                            time.perf_counter()
                            - started
                        ) * 1000,
                        3,
                    ),
                    "authentication_required": False,
                    "trading_endpoints_enabled": False,
                },
            )

        except Exception as exc:
            return ConnectorHealth(
                connector_id=self.connector_id,
                name=self.name,
                healthy=False,
                message=str(exc),
                capabilities=self.capabilities,
                metadata={
                    "authentication_required": False,
                    "trading_endpoints_enabled": False,
                },
            )

    async def list_markets(
        self,
        *,
        limit: int = 100,
    ) -> list[NormalizedMarket]:
        normalized_limit = max(
            1,
            min(int(limit), 1000),
        )

        payload = await self._get(
            "/markets",
            params={
                "status": "open",
                "limit": normalized_limit,
                "mve_filter": "exclude",
            },
        )

        raw_markets = (
            payload.get("markets", [])
            if isinstance(payload, Mapping)
            else []
        )

        markets: list[NormalizedMarket] = []

        for raw in raw_markets:
            if not isinstance(raw, Mapping):
                continue

            try:
                market = self._normalize_market(raw)
            except (TypeError, ValueError):
                continue

            if market.status == "OPEN":
                markets.append(market)

        return markets[:normalized_limit]

    async def get_snapshot(
        self,
        market_id: str,
    ) -> MarketSnapshot:
        ticker = str(market_id or "").strip()

        if not ticker:
            raise ValueError(
                "market_id Kalshi ? obrigat?rio."
            )

        started = time.perf_counter()
        encoded = quote(ticker, safe="")

        market_payload, book_payload = (
            await asyncio.gather(
                self._get(f"/markets/{encoded}"),
                self._get(
                    f"/markets/{encoded}/orderbook"
                ),
            )
        )

        raw = (
            market_payload.get("market", {})
            if isinstance(
                market_payload,
                Mapping,
            )
            else {}
        )

        if not isinstance(raw, Mapping):
            raise RuntimeError(
                "Resposta de mercado Kalshi inv?lida."
            )

        market = self._normalize_market(raw)

        book = {}

        if isinstance(book_payload, Mapping):
            book = (
                book_payload.get("orderbook_fp")
                or book_payload.get("orderbook")
                or {}
            )

        if not isinstance(book, Mapping):
            book = {}

        yes_bid, yes_bid_size = _best_bid(
            book.get("yes_dollars")
            or book.get("yes")
        )
        no_bid, no_bid_size = _best_bid(
            book.get("no_dollars")
            or book.get("no")
        )

        yes_bid = (
            yes_bid
            if yes_bid is not None
            else _number(
                raw.get("yes_bid_dollars")
                or raw.get("yes_bid")
            )
        )
        no_bid = (
            no_bid
            if no_bid is not None
            else _number(
                raw.get("no_bid_dollars")
                or raw.get("no_bid")
            )
        )

        yes_ask = (
            round(1 - no_bid, 10)
            if no_bid is not None
            else _number(
                raw.get("yes_ask_dollars")
                or raw.get("yes_ask")
            )
        )
        no_ask = (
            round(1 - yes_bid, 10)
            if yes_bid is not None
            else _number(
                raw.get("no_ask_dollars")
                or raw.get("no_ask")
            )
        )

        if (
            yes_bid is not None
            and yes_ask is not None
            and yes_bid > yes_ask
        ):
            yes_ask = None

        if (
            no_bid is not None
            and no_ask is not None
            and no_bid > no_ask
        ):
            no_ask = None

        last_yes = _number(
            raw.get("last_price_dollars")
            or raw.get("last_price")
        )
        last_no = (
            round(1 - last_yes, 10)
            if last_yes is not None
            else None
        )

        quotes = (
            MarketQuote(
                connector_id=self.connector_id,
                market_id=ticker,
                outcome_id="YES",
                bid=yes_bid,
                ask=yes_ask,
                last=last_yes,
                bid_size=yes_bid_size,
                ask_size=no_bid_size,
            ),
            MarketQuote(
                connector_id=self.connector_id,
                market_id=ticker,
                outcome_id="NO",
                bid=no_bid,
                ask=no_ask,
                last=last_no,
                bid_size=no_bid_size,
                ask_size=yes_bid_size,
            ),
        )

        return MarketSnapshot(
            market=market,
            quotes=quotes,
            captured_at=utc_now(),
            source_latency_ms=round(
                (
                    time.perf_counter()
                    - started
                ) * 1000,
                3,
            ),
            raw_reference=(
                f"{self.base_url}/markets/{encoded}"
            ),
            metadata={
                "platform": "kalshi",
                "authentication_required": False,
                "trading_endpoints_enabled": False,
                "read_only": True,
            },
        )


def build_kalshi_connector_from_env(
    *,
    transport: httpx.AsyncBaseTransport | None = None,
) -> KalshiReadOnlyConnector | None:
    if not _env_bool(
        "KALSHI_READ_ONLY_ENABLED",
        True,
    ):
        return None

    return KalshiReadOnlyConnector(
        base_url=os.getenv(
            "KALSHI_BASE_URL",
            OFFICIAL_BASE_URL,
        ),
        timeout_seconds=_env_float(
            "KALSHI_TIMEOUT_SECONDS",
            12.0,
        ),
        max_retries=_env_int(
            "KALSHI_MAX_RETRIES",
            2,
        ),
        default_market_limit=_env_int(
            "KALSHI_DEFAULT_MARKET_LIMIT",
            100,
        ),
        transport=transport,
        allow_insecure_http=_env_bool(
            "KALSHI_ALLOW_INSECURE_HTTP",
            False,
        ),
    )
