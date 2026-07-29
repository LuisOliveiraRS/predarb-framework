from __future__ import annotations

import asyncio

import pytest

from app.real_markets.matching import (
    ManualMarketMatchStore,
    MarketMatchingService,
    canonical_outcome_label,
    market_fingerprint,
    normalize_text,
    outcome_signature,
)
from app.real_markets.models import (
    MarketOutcome,
    NormalizedMarket,
)


def market(
    *,
    connector_id: str,
    market_id: str,
    title: str,
    close_time: str | None = (
        "2026-12-31T23:59:59+00:00"
    ),
    labels: tuple[str, ...] = (
        "Yes",
        "No",
    ),
    category: str | None = "crypto",
) -> NormalizedMarket:
    return NormalizedMarket(
        connector_id=connector_id,
        market_id=market_id,
        title=title,
        status="OPEN",
        outcomes=tuple(
            MarketOutcome(
                outcome_id=(
                    f"OUTCOME_{index}"
                ),
                label=label,
                token_id=(
                    f"{market_id}-{index}"
                ),
            )
            for index, label in enumerate(
                labels
            )
        ),
        close_time=close_time,
        category=category,
    )


class MarketDataStub:
    def __init__(
        self,
        markets,
    ):
        self.markets = list(markets)

    async def list_markets(
        self,
        *,
        connector_id=None,
        limit=100,
    ):
        selected = [
            item
            for item in self.markets
            if (
                connector_id is None
                or item.connector_id
                == connector_id
            )
        ]

        return selected[:limit]


def service(
    tmp_path,
    markets,
) -> MarketMatchingService:
    return MarketMatchingService(
        market_data_service=(
            MarketDataStub(markets)
        ),
        store=ManualMarketMatchStore(
            tmp_path
            / "manual_matches.json"
        ),
        candidate_threshold=0.55,
        strong_threshold=0.80,
    )


def test_text_normalization_removes_accents_and_stopwords():
    assert (
        normalize_text(
            "Bitcoin ficará acima de US$ 100 mil no fim de 2026?"
        )
        == "bitcoin acima us 100 mil 2026"
    )


def test_outcome_aliases_are_canonical():
    assert (
        canonical_outcome_label(
            "Sim"
        )
        == "YES"
    )
    assert (
        canonical_outcome_label(
            "Não"
        )
        == "NO"
    )

    sample = market(
        connector_id="a",
        market_id="1",
        title="Teste",
        labels=(
            "Sim",
            "Não",
        ),
    )

    assert outcome_signature(
        sample
    ) == (
        "NO",
        "YES",
    )


def test_fingerprint_is_stable_across_language_aliases():
    left = market(
        connector_id="a",
        market_id="1",
        title=(
            "Bitcoin ficará acima de US$ 100 mil no fim de 2026?"
        ),
        labels=(
            "Sim",
            "Não",
        ),
    )

    right = market(
        connector_id="b",
        market_id="2",
        title=(
            "Bitcoin acima de US$ 100 mil em 2026?"
        ),
        labels=(
            "Yes",
            "No",
        ),
    )

    assert (
        market_fingerprint(left)
        == market_fingerprint(right)
    )


def test_equivalent_markets_are_strong_candidates(
    tmp_path,
):
    left = market(
        connector_id="mock",
        market_id="btc",
        title=(
            "Bitcoin ficará acima de US$ 100 mil no fim de 2026?"
        ),
        labels=(
            "Sim",
            "Não",
        ),
    )

    right = market(
        connector_id="polymarket",
        market_id="btc-market",
        title=(
            "Bitcoin acima de US$ 100 mil em 2026?"
        ),
        labels=(
            "Yes",
            "No",
        ),
    )

    comparison = service(
        tmp_path,
        [
            left,
            right,
        ],
    ).compare(
        left,
        right,
    )

    assert (
        comparison.status
        == "STRONG_CANDIDATE"
    )
    assert comparison.score >= 0.80
    assert comparison.hard_rejected is False


def test_same_connector_is_rejected(
    tmp_path,
):
    left = market(
        connector_id="polymarket",
        market_id="one",
        title="Mercado equivalente",
    )

    right = market(
        connector_id="polymarket",
        market_id="two",
        title="Mercado equivalente",
    )

    comparison = service(
        tmp_path,
        [
            left,
            right,
        ],
    ).compare(
        left,
        right,
    )

    assert comparison.status == "REJECTED"
    assert comparison.hard_rejected is True
    assert (
        "SAME_CONNECTOR"
        in comparison.reasons
    )


def test_incompatible_outcomes_are_rejected(
    tmp_path,
):
    left = market(
        connector_id="a",
        market_id="one",
        title="Mesmo título",
        labels=(
            "Yes",
            "No",
        ),
    )

    right = market(
        connector_id="b",
        market_id="two",
        title="Mesmo título",
        labels=(
            "Home",
            "Draw",
            "Away",
        ),
    )

    comparison = service(
        tmp_path,
        [
            left,
            right,
        ],
    ).compare(
        left,
        right,
    )

    assert comparison.status == "REJECTED"
    assert comparison.hard_rejected is True
    assert (
        "OUTCOME_STRUCTURE_MISMATCH"
        in comparison.reasons
    )


def test_candidates_compare_only_requested_connectors(
    tmp_path,
):
    left = market(
        connector_id="a",
        market_id="one",
        title=(
            "Bitcoin acima de 100 mil em 2026"
        ),
    )

    right = market(
        connector_id="b",
        market_id="two",
        title=(
            "Bitcoin acima de 100 mil em 2026"
        ),
    )

    unrelated = market(
        connector_id="c",
        market_id="three",
        title="Outro mercado",
    )

    payload = asyncio.run(
        service(
            tmp_path,
            [
                left,
                right,
                unrelated,
            ],
        ).candidates(
            connector_a="a",
            connector_b="b",
            limit_per_connector=10,
        )
    )

    assert payload["compared_pairs"] == 1
    assert payload["count"] == 1
    assert (
        payload["candidates"][0][
            "left"
        ]["connector_id"]
        == "a"
    )
    assert (
        payload["candidates"][0][
            "right"
        ]["connector_id"]
        == "b"
    )
    assert (
        payload[
            "automatic_matching_authorized"
        ]
        is False
    )


def test_compare_keys_is_read_only(
    tmp_path,
):
    left = market(
        connector_id="a",
        market_id="one",
        title="Mercado comum",
    )

    right = market(
        connector_id="b",
        market_id="two",
        title="Mercado comum",
    )

    payload = asyncio.run(
        service(
            tmp_path,
            [
                left,
                right,
            ],
        ).compare_keys(
            left_connector_id="a",
            left_market_id="one",
            right_connector_id="b",
            right_market_id="two",
        )
    )

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True
    assert (
        payload[
            "automatic_matching_authorized"
        ]
        is False
    )
    assert payload["live_execution"] is False
    assert (
        payload["financial_execution"]
        is False
    )


def test_manual_match_persists_and_prevents_duplicate(
    tmp_path,
):
    left = market(
        connector_id="a",
        market_id="one",
        title="Mercado comum",
    )

    right = market(
        connector_id="b",
        market_id="two",
        title="Mercado comum",
    )

    matching = service(
        tmp_path,
        [
            left,
            right,
        ],
    )

    first = asyncio.run(
        matching.confirm_manual_match(
            left_connector_id="a",
            left_market_id="one",
            right_connector_id="b",
            right_market_id="two",
            note="Confirmado por revisão.",
        )
    )

    assert first["status"] == "CONFIRMED"
    assert (
        first["match"]["relation"]
        == "EQUIVALENT"
    )
    assert (
        first["next_step_authorized"]
        is False
    )

    with pytest.raises(
        ValueError,
        match="já está registrada",
    ):
        asyncio.run(
            matching.confirm_manual_match(
                left_connector_id="b",
                left_market_id="two",
                right_connector_id="a",
                right_market_id="one",
            )
        )


def test_manual_match_can_be_removed(
    tmp_path,
):
    left = market(
        connector_id="a",
        market_id="one",
        title="Mercado comum",
    )

    right = market(
        connector_id="b",
        market_id="two",
        title="Mercado comum",
    )

    matching = service(
        tmp_path,
        [
            left,
            right,
        ],
    )

    confirmed = asyncio.run(
        matching.confirm_manual_match(
            left_connector_id="a",
            left_market_id="one",
            right_connector_id="b",
            right_market_id="two",
        )
    )

    removed = (
        matching.remove_manual_match(
            confirmed["match"]["id"]
        )
    )

    assert removed["removed"] is True
    assert removed["status"] == "REMOVED"
    assert (
        matching.manual_matches()[
            "count"
        ]
        == 0
    )


def test_dashboard_contains_complete_confirmation_tokens():
    from app.api.routers import (
        market_matching
        as router_module,
    )

    response = asyncio.run(
        router_module
        .market_matching_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Identidade e Correspondência de Mercados"
        in body
    )
    assert (
        "CONFIRM-REAL-MARKET-MATCH"
        in body
    )
    assert (
        "REMOVE-REAL-MARKET-MATCH"
        in body
    )
    assert (
        "Correspondência automática desativada"
        in body
    )
    assert (
        response.headers[
            "x-predarb-automatic-matching"
        ]
        == "false"
    )


def test_manual_endpoint_requires_confirmation():
    from fastapi import HTTPException
    from app.api.routers import (
        market_matching
        as router_module,
    )

    request = (
        router_module
        .ManualMatchRequest(
            left_connector_id="a",
            left_market_id="one",
            right_connector_id="b",
            right_market_id="two",
        )
    )

    with pytest.raises(
        HTTPException,
    ) as exc:
        asyncio.run(
            router_module
            .market_matching_confirm_manual_match(
                request=request,
                confirm="INVALID",
            )
        )

    assert exc.value.status_code == 400


def test_application_registers_phase9c_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.market_matching import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/real-markets/matching/health",
        "/real-markets/matching/identities",
        "/real-markets/matching/compare",
        "/real-markets/matching/candidates",
        "/real-markets/matching/manual-matches",
        (
            "/real-markets/matching/"
            "manual-matches/{match_id}"
        ),
        "/real-markets/matching/dashboard",
        "/real-markets/matching/architecture",
    }

    assert not (
        required - paths
    )

    methods = {
        (
            route.path,
            tuple(
                sorted(
                    route.methods or set()
                )
            ),
        )
        for route in router.routes
    }

    assert (
        (
            "/real-markets/matching/"
            "manual-matches",
            ("GET",),
        )
        in methods
    )

    assert (
        (
            "/real-markets/matching/"
            "manual-matches",
            ("POST",),
        )
        in methods
    )

    assert (
        (
            "/real-markets/matching/"
            "manual-matches/{match_id}",
            ("DELETE",),
        )
        in methods
    )
