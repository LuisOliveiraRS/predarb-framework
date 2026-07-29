from __future__ import annotations

import asyncio
import json
import os
import re
import time
from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from urllib.parse import urlparse

import httpx

from app.real_markets.connectors import (
    ReadOnlyMarketConnector,
)
from app.real_markets.models import (
    ConnectorHealth,
    MarketOutcome,
    MarketQuote,
    MarketSnapshot,
    NormalizedMarket,
)


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _env_bool(
    name: str,
    default: bool,
) -> bool:
    value = os.getenv(name)

    if value is None:
        return bool(default)

    return value.strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
        "sim",
    }


def _env_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return float(default)

    try:
        return float(value)
    except ValueError:
        return float(default)


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


def _as_bool(
    value: Any,
    default: bool = False,
) -> bool:
    if value is None:
        return bool(default)

    if isinstance(value, bool):
        return value

    if isinstance(value, (int, float)):
        return bool(value)

    return str(value).strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _as_float(
    value: Any,
) -> float | None:
    if value in (
        None,
        "",
    ):
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _json_array(
    value: Any,
) -> list[Any]:
    if value is None:
        return []

    if isinstance(value, list):
        return list(value)

    if isinstance(value, tuple):
        return list(value)

    if isinstance(value, str):
        stripped = value.strip()

        if not stripped:
            return []

        try:
            parsed = json.loads(stripped)
        except json.JSONDecodeError:
            return [
                item.strip()
                for item in stripped.split(",")
                if item.strip()
            ]

        if isinstance(parsed, list):
            return parsed

    return []


def _slug_outcome_id(
    label: str,
    index: int,
    used: set[str],
) -> str:
    normalized = re.sub(
        r"[^A-Za-z0-9]+",
        "_",
        label.strip(),
    ).strip("_").upper()

    if not normalized:
        normalized = f"OUTCOME_{index + 1}"

    candidate = normalized
    suffix = 2

    while candidate in used:
        candidate = f"{normalized}_{suffix}"
        suffix += 1

    used.add(candidate)
    return candidate


def _validate_base_url(
    value: str,
    *,
    allow_insecure_http: bool,
) -> str:
    normalized = value.rstrip("/")
    parsed = urlparse(normalized)

    allowed_schemes = (
        {"https", "http"}
        if allow_insecure_http
        else {"https"}
    )

    if (
        parsed.scheme not in allowed_schemes
        or not parsed.netloc
    ):
        raise ValueError(
            "URL base inválida ou insegura: "
            f"{value}"
        )

    return normalized


class PolymarketReadOnlyConnector(
    ReadOnlyMarketConnector
):
    """Conector público de metadados e orderbook da Polymarket."""

    connector_id = "polymarket"
    name = "Polymarket Public Market Data"
    kind = "prediction_market"
    read_only = True

    def __init__(
        self,
        *,
        gamma_base_url: str = (
            "https://gamma-api.polymarket.com"
        ),
        clob_base_url: str = (
            "https://clob.polymarket.com"
        ),
        timeout_seconds: float = 12.0,
        max_retries: int = 2,
        retry_base_seconds: float = 0.25,
        default_market_limit: int = 50,
        transport: (
            httpx.AsyncBaseTransport
            | None
        ) = None,
        allow_insecure_http: bool = False,
    ) -> None:
        self.gamma_base_url = _validate_base_url(
            gamma_base_url,
            allow_insecure_http=allow_insecure_http,
        )

        self.clob_base_url = _validate_base_url(
            clob_base_url,
            allow_insecure_http=allow_insecure_http,
        )

        self.timeout_seconds = max(
            1.0,
            min(
                float(timeout_seconds),
                60.0,
            ),
        )

        self.max_retries = max(
            0,
            min(
                int(max_retries),
                5,
            ),
        )

        self.retry_base_seconds = max(
            0.0,
            min(
                float(retry_base_seconds),
                5.0,
            ),
        )

        self.default_market_limit = max(
            1,
            min(
                int(default_market_limit),
                250,
            ),
        )

        self.transport = transport

    @property
    def capabilities(
        self,
    ) -> tuple[str, ...]:
        return (
            "market_data",
            "quotes",
            "snapshots",
            "public_gamma_api",
            "public_clob_orderbook",
        )

    def descriptor(
        self,
    ) -> dict[str, Any]:
        payload = super().descriptor()

        payload.update(
            {
                "authentication_required": False,
                "trading_endpoints_enabled": False,
                "gamma_base_url": (
                    self.gamma_base_url
                ),
                "clob_base_url": (
                    self.clob_base_url
                ),
                "timeout_seconds": (
                    self.timeout_seconds
                ),
                "max_retries": (
                    self.max_retries
                ),
                "default_market_limit": (
                    self.default_market_limit
                ),
            }
        )

        return payload

    async def _request_json(
        self,
        *,
        base_url: str,
        path: str,
        params: Mapping[
            str,
            Any,
        ] | None = None,
    ) -> Any:
        last_error: Exception | None = None

        for attempt in range(
            self.max_retries + 1
        ):
            try:
                async with httpx.AsyncClient(
                    base_url=base_url,
                    timeout=self.timeout_seconds,
                    transport=self.transport,
                    headers={
                        "Accept": "application/json",
                        "User-Agent": (
                            "PredArb/9B "
                            "PolymarketReadOnlyConnector"
                        ),
                    },
                    follow_redirects=True,
                ) as client:
                    response = await client.get(
                        path,
                        params=params,
                    )

                if (
                    response.status_code == 429
                    or 500
                    <= response.status_code
                    <= 599
                ):
                    if attempt < self.max_retries:
                        retry_after = _as_float(
                            response.headers.get(
                                "retry-after"
                            )
                        )

                        delay = (
                            retry_after
                            if retry_after is not None
                            else (
                                self.retry_base_seconds
                                * (
                                    2 ** attempt
                                )
                            )
                        )

                        await asyncio.sleep(
                            max(0.0, delay)
                        )
                        continue

                response.raise_for_status()

                try:
                    return response.json()
                except ValueError:
                    body = response.text.strip()

                    if body:
                        return body

                    raise

            except (
                httpx.HTTPError,
                ValueError,
            ) as exc:
                last_error = exc

                if attempt >= self.max_retries:
                    break

                await asyncio.sleep(
                    self.retry_base_seconds
                    * (
                        2 ** attempt
                    )
                )

        raise RuntimeError(
            "Falha ao consultar a API pública "
            f"da Polymarket: {last_error}"
        ) from last_error

    async def _gamma(
        self,
        path: str,
        *,
        params: Mapping[
            str,
            Any,
        ] | None = None,
    ) -> Any:
        return await self._request_json(
            base_url=self.gamma_base_url,
            path=path,
            params=params,
        )

    async def _clob(
        self,
        path: str,
        *,
        params: Mapping[
            str,
            Any,
        ] | None = None,
    ) -> Any:
        return await self._request_json(
            base_url=self.clob_base_url,
            path=path,
            params=params,
        )

    @staticmethod
    def _status(
        raw: Mapping[str, Any],
    ) -> str:
        if _as_bool(
            raw.get("closed")
        ):
            return "CLOSED"

        if _as_bool(
            raw.get("archived")
        ):
            return "CLOSED"

        if _as_bool(
            raw.get("active"),
            default=True,
        ):
            return "OPEN"

        if (
            raw.get("resolved")
            is not None
            and _as_bool(
                raw.get("resolved")
            )
        ):
            return "RESOLVED"

        return "UNKNOWN"

    @staticmethod
    def _market_id(
        raw: Mapping[str, Any],
    ) -> str:
        value = (
            raw.get("id")
            or raw.get("marketId")
            or raw.get("market_id")
            or raw.get("conditionId")
            or raw.get("condition_id")
        )

        if value in (
            None,
            "",
        ):
            raise ValueError(
                "Mercado Polymarket sem identificador."
            )

        return str(value)

    @staticmethod
    def _labels_and_tokens(
        raw: Mapping[str, Any],
    ) -> tuple[
        list[str],
        list[str | None],
    ]:
        labels = [
            str(item)
            for item in _json_array(
                raw.get("outcomes")
            )
        ]

        tokens = [
            (
                None
                if item in (
                    None,
                    "",
                )
                else str(item)
            )
            for item in _json_array(
                raw.get("clobTokenIds")
                or raw.get(
                    "clob_token_ids"
                )
                or raw.get(
                    "tokens"
                )
            )
        ]

        if not labels:
            labels = [
                "Yes",
                "No",
            ]

        if len(tokens) < len(labels):
            tokens.extend(
                [None]
                * (
                    len(labels)
                    - len(tokens)
                )
            )

        if len(tokens) > len(labels):
            tokens = tokens[
                :len(labels)
            ]

        return labels, tokens

    @classmethod
    def _normalize_market(
        cls,
        raw: Mapping[str, Any],
        *,
        event: Mapping[
            str,
            Any,
        ] | None = None,
    ) -> NormalizedMarket:
        labels, tokens = (
            cls._labels_and_tokens(
                raw
            )
        )

        used: set[str] = set()
        outcomes = tuple(
            MarketOutcome(
                outcome_id=_slug_outcome_id(
                    label,
                    index,
                    used,
                ),
                label=label,
                token_id=tokens[index],
            )
            for index, label in enumerate(
                labels
            )
        )

        market_id = cls._market_id(
            raw
        )

        title = str(
            raw.get("question")
            or raw.get("title")
            or (
                event.get("title")
                if event
                else ""
            )
            or f"Polymarket {market_id}"
        )

        market_slug = (
            raw.get("slug")
            or (
                event.get("slug")
                if event
                else None
            )
        )

        event_id = (
            event.get("id")
            if event
            else raw.get("eventId")
        )

        event_slug = (
            event.get("slug")
            if event
            else raw.get("eventSlug")
        )

        source_slug = (
            event_slug
            or market_slug
        )

        source_url = (
            (
                "https://polymarket.com/"
                f"event/{source_slug}"
            )
            if source_slug
            else None
        )

        return NormalizedMarket(
            connector_id="polymarket",
            market_id=market_id,
            title=title,
            status=cls._status(raw),
            outcomes=outcomes,
            close_time=(
                raw.get("endDate")
                or raw.get("endDateIso")
                or raw.get("end_date")
            ),
            currency="pUSD",
            category=(
                raw.get("category")
                or (
                    event.get("category")
                    if event
                    else None
                )
            ),
            source_url=source_url,
            description=(
                raw.get("description")
                or (
                    event.get("description")
                    if event
                    else None
                )
            ),
            metadata={
                "platform": "polymarket",
                "gamma_market_id": market_id,
                "condition_id": (
                    raw.get("conditionId")
                    or raw.get(
                        "condition_id"
                    )
                ),
                "question_id": (
                    raw.get("questionID")
                    or raw.get("questionId")
                    or raw.get(
                        "question_id"
                    )
                ),
                "market_slug": market_slug,
                "event_id": event_id,
                "event_slug": event_slug,
                "accepting_orders": _as_bool(
                    raw.get(
                        "acceptingOrders"
                    )
                ),
                "enable_order_book": _as_bool(
                    raw.get(
                        "enableOrderBook"
                    ),
                    default=True,
                ),
                "neg_risk": _as_bool(
                    raw.get("negRisk")
                ),
                "liquidity": _as_float(
                    raw.get("liquidity")
                    or raw.get(
                        "liquidityNum"
                    )
                ),
                "volume": _as_float(
                    raw.get("volume")
                    or raw.get(
                        "volumeNum"
                    )
                ),
                "volume_24hr": _as_float(
                    raw.get("volume24hr")
                    or raw.get(
                        "volume_24hr"
                    )
                ),
                "authentication_required": False,
                "trading_endpoints_enabled": False,
            },
        )

    @staticmethod
    def _event_markets(
        payload: Any,
    ) -> list[
        tuple[
            Mapping[str, Any],
            Mapping[str, Any] | None,
        ]
    ]:
        if isinstance(payload, list):
            items = payload

        elif isinstance(payload, Mapping):
            items = (
                payload.get("data")
                or payload.get("events")
                or payload.get("markets")
                or []
            )

        else:
            items = []

        flattened: list[
            tuple[
                Mapping[str, Any],
                Mapping[str, Any] | None,
            ]
        ] = []

        for item in items:
            if not isinstance(
                item,
                Mapping,
            ):
                continue

            nested = item.get(
                "markets"
            )

            if isinstance(
                nested,
                Sequence,
            ) and not isinstance(
                nested,
                (
                    str,
                    bytes,
                ),
            ):
                for market in nested:
                    if isinstance(
                        market,
                        Mapping,
                    ):
                        flattened.append(
                            (
                                market,
                                item,
                            )
                        )
                continue

            flattened.append(
                (
                    item,
                    None,
                )
            )

        return flattened

    @staticmethod
    def _best_level(
        levels: Any,
        *,
        side: str,
    ) -> tuple[
        float | None,
        float | None,
    ]:
        if not isinstance(
            levels,
            Sequence,
        ) or isinstance(
            levels,
            (
                str,
                bytes,
            ),
        ):
            return None, None

        parsed: list[
            tuple[float, float | None]
        ] = []

        for level in levels:
            if not isinstance(
                level,
                Mapping,
            ):
                continue

            price = _as_float(
                level.get("price")
            )

            size = _as_float(
                level.get("size")
            )

            if price is None:
                continue

            parsed.append(
                (
                    price,
                    size,
                )
            )

        if not parsed:
            return None, None

        if side == "bid":
            return max(
                parsed,
                key=lambda item: item[0],
            )

        return min(
            parsed,
            key=lambda item: item[0],
        )

    async def health(
        self,
    ) -> ConnectorHealth:
        started = time.perf_counter()

        try:
            gamma_payload, clob_payload = (
                await asyncio.gather(
                    self._gamma(
                        "/events",
                        params={
                            "active": "true",
                            "closed": "false",
                            "limit": 1,
                        },
                    ),
                    self._clob("/ok"),
                )
            )

            gamma_valid = isinstance(
                gamma_payload,
                (
                    list,
                    Mapping,
                ),
            )

            clob_valid = (
                clob_payload is not None
            )

            healthy = (
                gamma_valid
                and clob_valid
            )

            return ConnectorHealth(
                connector_id=self.connector_id,
                name=self.name,
                healthy=healthy,
                message=(
                    "APIs públicas Gamma e CLOB "
                    "disponíveis."
                    if healthy
                    else (
                        "Resposta pública da "
                        "Polymarket inválida."
                    )
                ),
                capabilities=self.capabilities,
                metadata={
                    "gamma_reachable": gamma_valid,
                    "clob_reachable": clob_valid,
                    "latency_ms": round(
                        (
                            time.perf_counter()
                            - started
                        )
                        * 1000,
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
                    "gamma_reachable": False,
                    "clob_reachable": False,
                    "latency_ms": round(
                        (
                            time.perf_counter()
                            - started
                        )
                        * 1000,
                        3,
                    ),
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
            min(
                int(limit),
                250,
            ),
        )

        event_limit = max(
            1,
            min(
                normalized_limit,
                100,
            ),
        )

        payload = await self._gamma(
            "/events",
            params={
                "active": "true",
                "closed": "false",
                "limit": event_limit,
                "order": "volume24hr",
                "ascending": "false",
            },
        )

        markets: list[
            NormalizedMarket
        ] = []

        for raw, event in self._event_markets(
            payload
        ):
            try:
                market = self._normalize_market(
                    raw,
                    event=event,
                )
            except (
                TypeError,
                ValueError,
            ):
                continue

            if market.status != "OPEN":
                continue

            if not any(
                outcome.token_id
                for outcome in market.outcomes
            ):
                continue

            markets.append(market)

            if (
                len(markets)
                >= normalized_limit
            ):
                break

        return markets

    async def _fetch_market(
        self,
        market_id: str,
    ) -> Mapping[str, Any]:
        payload = await self._gamma(
            f"/markets/{market_id}"
        )

        if not isinstance(
            payload,
            Mapping,
        ):
            raise RuntimeError(
                "Resposta de mercado Polymarket inválida."
            )

        return payload

    async def _fetch_book(
        self,
        token_id: str,
    ) -> Mapping[str, Any] | None:
        try:
            payload = await self._clob(
                "/book",
                params={
                    "token_id": token_id,
                },
            )

        except RuntimeError as exc:
            cause = exc.__cause__

            if (
                isinstance(
                    cause,
                    httpx.HTTPStatusError,
                )
                and cause.response.status_code
                == 404
            ):
                return None

            raise

        if not isinstance(
            payload,
            Mapping,
        ):
            raise RuntimeError(
                "Orderbook Polymarket inválido."
            )

        return payload

    async def get_snapshot(
        self,
        market_id: str,
    ) -> MarketSnapshot:
        started = time.perf_counter()

        raw_market = await self._fetch_market(
            market_id
        )

        market = self._normalize_market(
            raw_market
        )

        token_outcomes = [
            outcome
            for outcome in market.outcomes
            if outcome.token_id
        ]

        if not token_outcomes:
            raise RuntimeError(
                "Mercado Polymarket sem token IDs públicos."
            )

        books = await asyncio.gather(
            *[
                self._fetch_book(
                    str(outcome.token_id)
                )
                for outcome in token_outcomes
            ],
            return_exceptions=True,
        )

        quotes: list[MarketQuote] = []
        book_errors: list[
            dict[str, str]
        ] = []

        for outcome, book in zip(
            token_outcomes,
            books,
            strict=True,
        ):
            if isinstance(
                book,
                Exception,
            ):
                book_errors.append(
                    {
                        "outcome_id": (
                            outcome.outcome_id
                        ),
                        "error": str(book),
                    }
                )

                quotes.append(
                    MarketQuote(
                        connector_id=self.connector_id,
                        market_id=market.market_id,
                        outcome_id=(
                            outcome.outcome_id
                        ),
                        bid=None,
                        ask=None,
                        last=None,
                        bid_size=None,
                        ask_size=None,
                    )
                )
                continue

            if book is None:
                quotes.append(
                    MarketQuote(
                        connector_id=self.connector_id,
                        market_id=market.market_id,
                        outcome_id=(
                            outcome.outcome_id
                        ),
                        bid=None,
                        ask=None,
                        last=None,
                        bid_size=None,
                        ask_size=None,
                    )
                )
                continue

            bid, bid_size = self._best_level(
                book.get("bids"),
                side="bid",
            )

            ask, ask_size = self._best_level(
                book.get("asks"),
                side="ask",
            )

            last = _as_float(
                book.get(
                    "last_trade_price"
                )
                or book.get(
                    "lastTradePrice"
                )
            )

            quotes.append(
                MarketQuote(
                    connector_id=self.connector_id,
                    market_id=market.market_id,
                    outcome_id=(
                        outcome.outcome_id
                    ),
                    bid=bid,
                    ask=ask,
                    last=last,
                    bid_size=bid_size,
                    ask_size=ask_size,
                )
            )

        return MarketSnapshot(
            market=market,
            quotes=tuple(quotes),
            captured_at=_utc_now(),
            source_latency_ms=round(
                (
                    time.perf_counter()
                    - started
                )
                * 1000,
                3,
            ),
            raw_reference=(
                f"{self.gamma_base_url}"
                f"/markets/{market_id}"
            ),
            metadata={
                "platform": "polymarket",
                "gamma_api": (
                    self.gamma_base_url
                ),
                "clob_api": (
                    self.clob_base_url
                ),
                "orderbooks_requested": len(
                    token_outcomes
                ),
                "orderbook_errors": (
                    book_errors
                ),
                "authentication_required": False,
                "trading_endpoints_enabled": False,
                "read_only": True,
            },
        )


def build_polymarket_connector_from_env(
    *,
    transport: (
        httpx.AsyncBaseTransport
        | None
    ) = None,
) -> PolymarketReadOnlyConnector | None:
    if not _env_bool(
        "POLYMARKET_READ_ONLY_ENABLED",
        True,
    ):
        return None

    return PolymarketReadOnlyConnector(
        gamma_base_url=os.getenv(
            "POLYMARKET_GAMMA_BASE_URL",
            "https://gamma-api.polymarket.com",
        ),
        clob_base_url=os.getenv(
            "POLYMARKET_CLOB_BASE_URL",
            "https://clob.polymarket.com",
        ),
        timeout_seconds=_env_float(
            "POLYMARKET_TIMEOUT_SECONDS",
            12.0,
        ),
        max_retries=_env_int(
            "POLYMARKET_MAX_RETRIES",
            2,
        ),
        retry_base_seconds=_env_float(
            "POLYMARKET_RETRY_BASE_SECONDS",
            0.25,
        ),
        default_market_limit=_env_int(
            "POLYMARKET_DEFAULT_MARKET_LIMIT",
            50,
        ),
        transport=transport,
        allow_insecure_http=_env_bool(
            "POLYMARKET_ALLOW_INSECURE_HTTP",
            False,
        ),
    )
