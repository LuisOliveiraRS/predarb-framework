from __future__ import annotations

from collections.abc import Iterable, Mapping
from itertools import combinations
from math import isfinite
from typing import Any

from app.engine.opportunity_builder import (
    OpportunityBuilder,
    opportunity_builder,
)
from app.market.market_matcher import (
    MarketMatcher,
    market_matcher,
)
from app.market.normalizer import normalizer


class CrossPlatformComparator:
    """
    Compara mercados equivalentes entre
    plataformas diferentes.

    Para cada par compatível, avalia:

    1. Yes no mercado A + No no mercado B;
    2. Yes no mercado B + No no mercado A.

    Quando diferentes mercados produzirem a mesma
    rota para o mesmo evento, somente a melhor
    oportunidade será preservada.
    """

    def __init__(
        self,
        *,
        matcher: MarketMatcher | None = None,
        builder: OpportunityBuilder | None = None,
    ) -> None:
        self.matcher = (
            matcher
            or market_matcher
        )

        self.builder = (
            builder
            or opportunity_builder
        )

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um campo de dicionário
        ou objeto.
        """

        if isinstance(
            target,
            Mapping,
        ):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @classmethod
    def _platform(
        cls,
        market: Any,
    ) -> str:
        """
        Recupera o nome da plataforma.
        """

        platform = cls._read_field(
            market,
            "platform",
            "",
        )

        return str(
            platform
        ).strip()

    @staticmethod
    def _canonical_text(
        value: Any,
    ) -> str:
        """
        Normaliza textos usados nas chaves
        de consolidação.
        """

        if value is None:
            return ""

        return (
            str(value)
            .strip()
            .casefold()
        )

    @classmethod
    def _canonical_question(
        cls,
        value: Any,
    ) -> str:
        """
        Normaliza a pergunta do evento.
        """

        raw_question = str(
            value
            or ""
        ).strip()

        if not raw_question:
            return ""

        normalized = normalizer.normalize(
            raw_question
        )

        if not isinstance(
            normalized,
            str,
        ):
            normalized = raw_question

        return normalized.strip().casefold()

    @staticmethod
    def _number(
        value: Any,
        *,
        default: float,
    ) -> float:
        """
        Converte valores utilizados na
        comparação das oportunidades.
        """

        if (
            value is None
            or isinstance(
                value,
                bool,
            )
        ):
            return float(default)

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ):
            return float(default)

        if not isfinite(
            number
        ):
            return float(default)

        return number

    @classmethod
    def _event_key(
        cls,
        opportunity: Mapping[str, Any],
    ) -> tuple[str, str, str, str]:
        """
        Gera uma assinatura do evento.

        A pergunta é o identificador principal.
        Asset, tipo de evento e expiração ajudam
        a impedir a consolidação de eventos
        diferentes com textos semelhantes.
        """

        market_yes = opportunity.get(
            "market_yes",
            {},
        )

        market_no = opportunity.get(
            "market_no",
            {},
        )

        question = opportunity.get(
            "question",
            "",
        )

        asset = cls._read_field(
            market_yes,
            "asset",
            "",
        ) or cls._read_field(
            market_no,
            "asset",
            "",
        )

        event_type = cls._read_field(
            market_yes,
            "event_type",
            "",
        ) or cls._read_field(
            market_no,
            "event_type",
            "",
        )

        expires_at = cls._read_field(
            market_yes,
            "expires_at",
            "",
        ) or cls._read_field(
            market_no,
            "expires_at",
            "",
        )

        return (
            cls._canonical_question(
                question
            ),
            cls._canonical_text(
                asset
            ),
            cls._canonical_text(
                event_type
            ),
            cls._canonical_text(
                expires_at
            ),
        )

    @classmethod
    def _route_key(
        cls,
        opportunity: Mapping[str, Any],
    ) -> tuple[
        tuple[str, str, str, str],
        str,
        str,
    ]:
        """
        Identifica uma rota de arbitragem:

        evento + plataforma Yes + plataforma No.
        """

        return (
            cls._event_key(
                opportunity
            ),
            cls._canonical_text(
                opportunity.get(
                    "buy_yes_platform",
                    "",
                )
            ),
            cls._canonical_text(
                opportunity.get(
                    "buy_no_platform",
                    "",
                )
            ),
        )

    @classmethod
    def _quality_key(
        cls,
        opportunity: Mapping[str, Any],
    ) -> tuple[
        float,
        float,
        float,
        float,
    ]:
        """
        Define qual oportunidade é melhor.

        Prioridades:

        1. menor custo;
        2. maior lucro;
        3. maior ROI;
        4. maior liquidez disponível.
        """

        cost = cls._number(
            opportunity.get(
                "cost"
            ),
            default=float("inf"),
        )

        profit = cls._number(
            opportunity.get(
                "profit"
            ),
            default=0.0,
        )

        roi = cls._number(
            opportunity.get(
                "roi"
            ),
            default=0.0,
        )

        volume_yes = cls._number(
            opportunity.get(
                "volume_yes"
            ),
            default=0.0,
        )

        volume_no = cls._number(
            opportunity.get(
                "volume_no"
            ),
            default=0.0,
        )

        available_volume = min(
            volume_yes,
            volume_no,
        )

        # A menor tupla vence.
        return (
            cost,
            -profit,
            -roi,
            -available_volume,
        )

    @classmethod
    def _is_better(
        cls,
        candidate: Mapping[str, Any],
        current: Mapping[str, Any],
    ) -> bool:
        """
        Compara duas oportunidades da mesma rota.
        """

        return (
            cls._quality_key(
                candidate
            )
            < cls._quality_key(
                current
            )
        )

    @staticmethod
    def _add_consolidation_metadata(
        opportunity: dict[str, Any],
        *,
        candidates: int,
    ) -> None:
        """
        Registra quantos candidatos foram
        consolidados na oportunidade final.
        """

        metadata = opportunity.get(
            "metadata"
        )

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

            opportunity["metadata"] = metadata

        metadata["route_candidates"] = (
            candidates
        )

        metadata["duplicates_collapsed"] = max(
            0,
            candidates - 1,
        )

        metadata["selection_rule"] = (
            "lowest_cost"
        )

    def compare(
        self,
        markets: Iterable[Any] | None,
    ) -> list[dict[str, Any]]:
        """
        Localiza e consolida oportunidades
        entre mercados.
        """

        if markets is None:
            return []

        if isinstance(
            markets,
            (str, bytes, Mapping),
        ):
            raise TypeError(
                "markets deve ser uma coleção "
                "de mercados."
            )

        market_list = list(
            markets
        )

        if len(
            market_list
        ) < 2:
            return []

        best_by_route: dict[
            tuple[
                tuple[str, str, str, str],
                str,
                str,
            ],
            dict[str, Any],
        ] = {}

        candidate_counts: dict[
            tuple[
                tuple[str, str, str, str],
                str,
                str,
            ],
            int,
        ] = {}

        for market_a, market_b in combinations(
            market_list,
            2,
        ):
            platform_a = self._platform(
                market_a
            )

            platform_b = self._platform(
                market_b
            )

            if (
                not platform_a
                or not platform_b
            ):
                continue

            # Não compara dois mercados
            # da mesma plataforma.
            if (
                platform_a.casefold()
                == platform_b.casefold()
            ):
                continue

            match = self.matcher.compare(
                market_a,
                market_b,
            )

            if not match["matched"]:
                continue

            directions = (
                (
                    market_a,
                    market_b,
                ),
                (
                    market_b,
                    market_a,
                ),
            )

            for market_yes, market_no in directions:
                opportunity = self.builder.build(
                    market_yes,
                    market_no,
                    similarity=(
                        match["similarity"]
                    ),
                )

                if opportunity is None:
                    continue

                route_key = self._route_key(
                    opportunity
                )

                candidate_counts[
                    route_key
                ] = (
                    candidate_counts.get(
                        route_key,
                        0,
                    )
                    + 1
                )

                current = best_by_route.get(
                    route_key
                )

                if (
                    current is None
                    or self._is_better(
                        opportunity,
                        current,
                    )
                ):
                    best_by_route[
                        route_key
                    ] = opportunity

        opportunities = list(
            best_by_route.values()
        )

        for opportunity in opportunities:
            route_key = self._route_key(
                opportunity
            )

            self._add_consolidation_metadata(
                opportunity,
                candidates=(
                    candidate_counts.get(
                        route_key,
                        1,
                    )
                ),
            )

        opportunities.sort(
            key=self._quality_key
        )

        return opportunities


cross_platform_comparator = (
    CrossPlatformComparator()
)