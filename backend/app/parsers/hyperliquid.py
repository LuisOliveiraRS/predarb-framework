from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from math import isfinite
from typing import Any


class HyperliquidParser:
    """
    Transforma metadados HIP-4 e preços allMids
    no formato utilizado atualmente pelo PredArb.

    Entrada esperada:

        {
            "metadata": {
                "outcomes": [...]
            },
            "mids": {
                "#<encoding>": "<price>"
            }
        }
    """

    PLATFORM = "Hyperliquid"
    CONNECTOR = "hyperliquid"

    @staticmethod
    def _to_outcome_id(
        value: Any,
    ) -> int | None:
        """
        Converte o identificador do outcome.
        """

        if isinstance(value, bool):
            return None

        try:
            outcome_id = int(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

        if outcome_id < 0:
            return None

        return outcome_id

    @staticmethod
    def _to_probability(
        value: Any,
    ) -> float | None:
        """
        Converte um preço HIP-4 em probabilidade.
        """

        if value is None or isinstance(
            value,
            bool,
        ):
            return None

        try:
            probability = float(value)

        except (
            TypeError,
            ValueError,
        ):
            return None

        if not isfinite(probability):
            return None

        if not 0 <= probability <= 1:
            return None

        return round(
            probability,
            6,
        )

    @staticmethod
    def _side_name(
        side_spec: Any,
        fallback: str,
    ) -> str:
        """
        Recupera o nome de um lado do outcome.
        """

        if isinstance(
            side_spec,
            Mapping,
        ):
            name = side_spec.get(
                "name"
            )

            if isinstance(name, str):
                normalized = name.strip()

                if normalized:
                    return normalized

        return fallback

    @staticmethod
    def _description_fields(
        description: Any,
    ) -> dict[str, str]:
        """
        Interpreta descrições estruturadas no formato:

            chave:valor|chave:valor
        """

        if not isinstance(
            description,
            str,
        ):
            return {}

        fields: dict[str, str] = {}

        for item in description.split("|"):
            if ":" not in item:
                continue

            key, value = item.split(
                ":",
                1,
            )

            normalized_key = key.strip()
            normalized_value = value.strip()

            if (
                normalized_key
                and normalized_value
            ):
                fields[
                    normalized_key
                ] = normalized_value

        return fields

    @staticmethod
    def _question(
        outcome: Mapping[str, Any],
        outcome_id: int,
    ) -> str:
        """
        Recupera a descrição mais fiel disponível.

        Não cria uma pergunta artificial quando
        o payload não fornece uma explicitamente.
        """

        for field_name in (
            "question",
            "title",
            "description",
            "name",
        ):
            value = outcome.get(
                field_name
            )

            if isinstance(value, str):
                normalized = value.strip()

                if normalized:
                    return normalized

        return (
            "Hyperliquid outcome "
            f"{outcome_id}"
        )

    @staticmethod
    def _side_indexes(
        side_specs: Sequence[Any],
    ) -> tuple[int, int] | None:
        """
        Localiza os lados Yes e No.

        Quando os nomes não forem literalmente
        Yes/No, utiliza os índices 0 e 1 e preserva
        os nomes originais nos metadados.
        """

        if len(side_specs) < 2:
            return None

        yes_index: int | None = None
        no_index: int | None = None

        for index, side_spec in enumerate(
            side_specs
        ):
            name = (
                HyperliquidParser._side_name(
                    side_spec,
                    "",
                )
                .strip()
                .lower()
            )

            if name == "yes":
                yes_index = index

            elif name == "no":
                no_index = index

        if (
            yes_index is not None
            and no_index is not None
        ):
            return (
                yes_index,
                no_index,
            )

        return (
            0,
            1,
        )

    def _parse_outcome(
        self,
        outcome: Mapping[str, Any],
        mids: Mapping[str, Any],
    ) -> dict[str, Any] | None:
        """
        Converte um único outcome.
        """

        outcome_id = self._to_outcome_id(
            outcome.get(
                "outcome"
            )
        )

        if outcome_id is None:
            return None

        side_specs = outcome.get(
            "sideSpecs"
        )

        if (
            not isinstance(
                side_specs,
                Sequence,
            )
            or isinstance(
                side_specs,
                (str, bytes),
            )
        ):
            return None

        indexes = self._side_indexes(
            side_specs
        )

        if indexes is None:
            return None

        yes_index, no_index = indexes

        yes_encoding = (
            10 * outcome_id
            + yes_index
        )

        no_encoding = (
            10 * outcome_id
            + no_index
        )

        yes_coin = f"#{yes_encoding}"
        no_coin = f"#{no_encoding}"

        yes_price = self._to_probability(
            mids.get(
                yes_coin
            )
        )

        no_price = self._to_probability(
            mids.get(
                no_coin
            )
        )

        # Não calculamos um lado como 1 - outro.
        # Cada preço deve vir do livro oficial.
        if (
            yes_price is None
            or no_price is None
        ):
            return None

        yes_label = self._side_name(
            side_specs[yes_index],
            "Yes",
        )

        no_label = self._side_name(
            side_specs[no_index],
            "No",
        )

        description = outcome.get(
            "description"
        )

        description_fields = (
            self._description_fields(
                description
            )
        )

        now = datetime.now(
            timezone.utc,
        ).isoformat()

        return {
            "platform": self.PLATFORM,
            "connector": self.CONNECTOR,
            "question": self._question(
                outcome,
                outcome_id,
            ),
            "yes": yes_price,
            "no": no_price,
            "liquidity": 0.0,
            "volume": 0.0,
            "fee": 0.0,
            "market_id": (
                f"hyperliquid:hip4:"
                f"{outcome_id}"
            ),
            "category": "outcome",
            "asset": description_fields.get(
                "underlying",
                "",
            ),
            "event_type": (
                description_fields.get(
                    "class",
                    "outcome",
                )
            ),
            "status": "open",
            "created_at": now,
            "metadata": {
                "outcome_id": outcome_id,
                "description": description,
                "description_fields": (
                    description_fields
                ),
                "yes": {
                    "label": yes_label,
                    "index": yes_index,
                    "encoding": yes_encoding,
                    "coin": yes_coin,
                },
                "no": {
                    "label": no_label,
                    "index": no_index,
                    "encoding": no_encoding,
                    "coin": no_coin,
                },
                "raw": dict(outcome),
            },
        }

    def parse(
        self,
        raw_markets: Any,
    ) -> list[dict[str, Any]]:
        """
        Converte o snapshot completo em mercados.
        """

        if not isinstance(
            raw_markets,
            Mapping,
        ):
            return []

        metadata = raw_markets.get(
            "metadata"
        )

        if metadata is None:
            metadata = raw_markets.get(
                "outcome_meta"
            )

        if metadata is None:
            metadata = raw_markets

        mids = raw_markets.get(
            "mids",
            {},
        )

        if not isinstance(
            metadata,
            Mapping,
        ):
            return []

        if not isinstance(
            mids,
            Mapping,
        ):
            return []

        outcomes = metadata.get(
            "outcomes",
            [],
        )

        if (
            not isinstance(
                outcomes,
                Sequence,
            )
            or isinstance(
                outcomes,
                (str, bytes),
            )
        ):
            return []

        markets: list[
            dict[str, Any]
        ] = []

        for outcome in outcomes:
            if not isinstance(
                outcome,
                Mapping,
            ):
                continue

            market = self._parse_outcome(
                outcome,
                mids,
            )

            if market is not None:
                markets.append(
                    market
                )

        return markets


hyperliquid_parser = HyperliquidParser()