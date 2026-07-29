from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import copy
from dataclasses import is_dataclass, replace
from typing import Any


class MarketService:
    """
    Serviço responsável por operações de domínio
    relacionadas aos mercados.

    A normalização preserva o tipo recebido:

    - dict entra como dict e retorna dict;
    - dataclass retorna a mesma classe;
    - modelo Pydantic retorna o mesmo modelo;
    - objeto comum é copiado antes da alteração.
    """

    @staticmethod
    def _normalize_text(
        value: Any,
        field_name: str,
        *,
        lowercase: bool = False,
    ) -> str:
        """
        Valida e normaliza um campo textual.
        """

        if not isinstance(value, str):
            raise TypeError(
                f"O campo {field_name!r} deve ser uma string."
            )

        normalized = value.strip()

        if not normalized:
            raise ValueError(
                f"O campo {field_name!r} não pode ser vazio."
            )

        if lowercase:
            normalized = normalized.lower()

        return normalized

    @staticmethod
    def _read_field(
        market: Any,
        field_name: str,
    ) -> Any:
        """
        Recupera um campo de dicionário ou objeto.
        """

        if isinstance(market, Mapping):
            if field_name not in market:
                raise ValueError(
                    f"Mercado sem o campo obrigatório "
                    f"{field_name!r}."
                )

            return market[field_name]

        if not hasattr(market, field_name):
            raise ValueError(
                f"Mercado sem o atributo obrigatório "
                f"{field_name!r}."
            )

        return getattr(
            market,
            field_name,
        )

    @staticmethod
    def _copy_with_updates(
        market: Any,
        updates: dict[str, Any],
    ) -> Any:
        """
        Cria uma cópia do mercado aplicando
        os campos normalizados.
        """

        if isinstance(market, Mapping):
            result = dict(market)
            result.update(updates)
            return result

        if is_dataclass(market):
            return replace(
                market,
                **updates,
            )

        model_copy = getattr(
            market,
            "model_copy",
            None,
        )

        if callable(model_copy):
            return model_copy(
                update=updates,
            )

        pydantic_fields = getattr(
            market,
            "__fields__",
            None,
        )

        object_copy = getattr(
            market,
            "copy",
            None,
        )

        if (
            pydantic_fields is not None
            and callable(object_copy)
        ):
            return object_copy(
                update=updates,
            )

        result = copy(market)

        for field_name, value in updates.items():
            setattr(
                result,
                field_name,
                value,
            )

        return result

    def normalize_market(
        self,
        market: Any,
    ) -> Any:
        """
        Normaliza um único mercado.
        """

        if market is None:
            raise ValueError(
                "Não é possível normalizar um mercado None."
            )

        question = self._normalize_text(
            self._read_field(
                market,
                "question",
            ),
            "question",
        )

        platform = self._normalize_text(
            self._read_field(
                market,
                "platform",
            ),
            "platform",
            lowercase=True,
        )

        return self._copy_with_updates(
            market,
            {
                "question": question,
                "platform": platform,
            },
        )

    def normalize(
        self,
        markets: Iterable[Any] | None,
    ) -> list[Any]:
        """
        Normaliza uma coleção de mercados.
        """

        if markets is None:
            return []

        if isinstance(
            markets,
            (str, bytes),
        ):
            raise TypeError(
                "A coleção de mercados não pode "
                "ser uma string."
            )

        return [
            self.normalize_market(market)
            for market in markets
        ]


market_service = MarketService()