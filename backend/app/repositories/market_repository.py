from __future__ import annotations

from collections.abc import Iterable, Mapping
from datetime import datetime, timezone
from math import isfinite
from threading import RLock
from typing import Any

from app.market.models import Market


_MISSING = object()


class MarketRepository:
    """
    Repositório oficial e thread-safe de mercados.

    Toda a aplicação recebe objetos Market,
    independentemente do formato retornado
    pelos conectores.

    A substituição dos mercados é atômica:
    caso algum item seja inválido, os dados
    anteriores permanecem preservados.
    """

    def __init__(self) -> None:
        self._markets: list[Market] = []
        self._lock = RLock()
        self._updated_at: datetime | None = None

    @staticmethod
    def _read_field(
        source: Any,
        field_name: str,
        default: Any = _MISSING,
    ) -> Any:
        """
        Recupera um valor de dicionário
        ou objeto.
        """

        if isinstance(source, Mapping):
            if field_name in source:
                return source[field_name]

        elif source is not None and hasattr(
            source,
            field_name,
        ):
            return getattr(
                source,
                field_name,
            )

        if default is not _MISSING:
            return default

        raise ValueError(
            "Mercado sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _text(
        value: Any,
        field_name: str,
        *,
        default: str | None = None,
        lowercase: bool = False,
    ) -> str:
        """
        Valida e normaliza campos textuais.
        """

        if value is None:
            if default is not None:
                return default

            raise ValueError(
                f"O campo {field_name!r} não pode ser None."
            )

        if not isinstance(value, str):
            value = str(value)

        normalized = value.strip()

        if not normalized:
            if default is not None:
                return default

            raise ValueError(
                f"O campo {field_name!r} não pode ser vazio."
            )

        if lowercase:
            return normalized.lower()

        return normalized

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
        *,
        default: float | None = None,
        minimum: float | None = None,
        maximum: float | None = None,
    ) -> float:
        """
        Valida e converte campos numéricos.
        """

        if value is None and default is not None:
            return float(default)

        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} não pode ser booleano."
            )

        try:
            number = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve ser numérico."
            ) from exc

        if not isfinite(number):
            raise ValueError(
                f"O campo {field_name!r} deve ser finito."
            )

        if minimum is not None and number < minimum:
            raise ValueError(
                f"O campo {field_name!r} não pode ser "
                f"menor que {minimum}."
            )

        if maximum is not None and number > maximum:
            raise ValueError(
                f"O campo {field_name!r} não pode ser "
                f"maior que {maximum}."
            )

        return number

    @staticmethod
    def _datetime(
        value: Any,
        field_name: str,
        *,
        default_now: bool = False,
        allow_none: bool = False,
    ) -> datetime | None:
        """
        Converte datetime ou string ISO-8601.
        """

        if value is None:
            if allow_none:
                return None

            if default_now:
                return datetime.now(
                    timezone.utc,
                )

            raise ValueError(
                f"O campo {field_name!r} é obrigatório."
            )

        if isinstance(value, datetime):
            if value.tzinfo is None:
                return value.replace(
                    tzinfo=timezone.utc,
                )

            return value

        if isinstance(value, str):
            normalized = value.strip()

            if not normalized:
                if allow_none:
                    return None

                if default_now:
                    return datetime.now(
                        timezone.utc,
                    )

                raise ValueError(
                    f"O campo {field_name!r} está vazio."
                )

            if normalized.endswith("Z"):
                normalized = (
                    normalized[:-1]
                    + "+00:00"
                )

            try:
                parsed = datetime.fromisoformat(
                    normalized,
                )

            except ValueError as exc:
                raise ValueError(
                    f"O campo {field_name!r} não possui "
                    "uma data ISO-8601 válida."
                ) from exc

            if parsed.tzinfo is None:
                parsed = parsed.replace(
                    tzinfo=timezone.utc,
                )

            return parsed

        raise TypeError(
            f"O campo {field_name!r} deve ser "
            "datetime ou string ISO-8601."
        )

    @staticmethod
    def _metadata(
        value: Any,
    ) -> dict[str, Any]:
        """
        Normaliza os metadados do mercado.
        """

        if value is None:
            return {}

        if not isinstance(value, Mapping):
            raise TypeError(
                "O campo 'metadata' deve ser um dicionário."
            )

        return dict(value)

    def _to_market(
        self,
        source: Any,
    ) -> Market:
        """
        Converte dicionários, dataclasses ou
        objetos compatíveis para Market.
        """

        if source is None:
            raise ValueError(
                "Não é possível armazenar um mercado None."
            )

        return Market(
            platform=self._text(
                self._read_field(
                    source,
                    "platform",
                ),
                "platform",
            ),
            question=self._text(
                self._read_field(
                    source,
                    "question",
                ),
                "question",
            ),
            yes=self._number(
                self._read_field(
                    source,
                    "yes",
                ),
                "yes",
                minimum=0.0,
                maximum=1.0,
            ),
            no=self._number(
                self._read_field(
                    source,
                    "no",
                ),
                "no",
                minimum=0.0,
                maximum=1.0,
            ),
            created_at=self._datetime(
                self._read_field(
                    source,
                    "created_at",
                    None,
                ),
                "created_at",
                default_now=True,
            ),
            connector=self._text(
                self._read_field(
                    source,
                    "connector",
                    "",
                ),
                "connector",
                default="unknown",
                lowercase=True,
            ),
            liquidity=self._number(
                self._read_field(
                    source,
                    "liquidity",
                    0.0,
                ),
                "liquidity",
                default=0.0,
                minimum=0.0,
            ),
            volume=self._number(
                self._read_field(
                    source,
                    "volume",
                    0.0,
                ),
                "volume",
                default=0.0,
                minimum=0.0,
            ),
            fee=self._number(
                self._read_field(
                    source,
                    "fee",
                    0.0,
                ),
                "fee",
                default=0.0,
                minimum=0.0,
            ),
            market_id=self._text(
                self._read_field(
                    source,
                    "market_id",
                    "",
                ),
                "market_id",
                default="",
            ),
            category=self._text(
                self._read_field(
                    source,
                    "category",
                    "",
                ),
                "category",
                default="",
            ),
            asset=self._text(
                self._read_field(
                    source,
                    "asset",
                    "",
                ),
                "asset",
                default="",
            ),
            event_type=self._text(
                self._read_field(
                    source,
                    "event_type",
                    "",
                ),
                "event_type",
                default="",
            ),
            expires_at=self._datetime(
                self._read_field(
                    source,
                    "expires_at",
                    None,
                ),
                "expires_at",
                allow_none=True,
            ),
            status=self._text(
                self._read_field(
                    source,
                    "status",
                    "open",
                ),
                "status",
                default="open",
                lowercase=True,
            ),
            metadata=self._metadata(
                self._read_field(
                    source,
                    "metadata",
                    {},
                )
            ),
        )

    @staticmethod
    def _deduplicate(
        markets: list[Market],
    ) -> list[Market]:
        """
        Remove mercados duplicados quando existe
        um market_id válido.

        Mercados sem market_id são preservados.
        """

        result: list[Market] = []
        seen: set[tuple[str, str]] = set()

        for market in markets:
            if not market.market_id:
                result.append(market)
                continue

            identity = (
                market.connector.lower(),
                market.market_id,
            )

            if identity in seen:
                continue

            seen.add(identity)
            result.append(market)

        return result

    def save_all(
        self,
        markets: Iterable[Any] | None,
    ) -> int:
        """
        Substitui atomicamente os mercados.

        Retorna a quantidade armazenada.
        """

        if markets is None:
            market_list: list[Any] = []

        elif isinstance(
            markets,
            (str, bytes, Mapping),
        ):
            raise TypeError(
                "markets deve ser uma coleção de mercados."
            )

        else:
            market_list = list(markets)

        normalized = [
            self._to_market(market)
            for market in market_list
        ]

        normalized = self._deduplicate(
            normalized,
        )

        with self._lock:
            self._markets = normalized
            self._updated_at = datetime.now(
                timezone.utc,
            )

        return len(normalized)

    def add(
        self,
        market: Any,
    ) -> Market:
        """
        Adiciona um mercado normalizado.
        """

        normalized = self._to_market(
            market,
        )

        with self._lock:
            self._markets.append(
                normalized,
            )

            self._updated_at = datetime.now(
                timezone.utc,
            )

        return normalized

    def all(self) -> list[Market]:
        """
        Retorna uma cópia dos mercados.
        """

        with self._lock:
            return list(
                self._markets,
            )

    def clear(self) -> None:
        """
        Remove todos os mercados.
        """

        with self._lock:
            self._markets.clear()
            self._updated_at = datetime.now(
                timezone.utc,
            )

    def count(self) -> int:
        with self._lock:
            return len(
                self._markets,
            )

    def get(
        self,
        market_id: str,
    ) -> Market | None:
        """
        Localiza um mercado pelo ID.
        """

        normalized_id = self._text(
            market_id,
            "market_id",
        )

        with self._lock:
            for market in self._markets:
                if market.market_id == normalized_id:
                    return market

        return None

    def by_platform(
        self,
        platform: str,
    ) -> list[Market]:
        """
        Filtra mercados por plataforma.
        """

        normalized_platform = self._text(
            platform,
            "platform",
        ).casefold()

        with self._lock:
            return [
                market
                for market in self._markets
                if market.platform.casefold()
                == normalized_platform
            ]

    def by_connector(
        self,
        connector: str,
    ) -> list[Market]:
        """
        Filtra mercados pelo conector de origem.
        """

        normalized_connector = self._text(
            connector,
            "connector",
        ).casefold()

        with self._lock:
            return [
                market
                for market in self._markets
                if market.connector.casefold()
                == normalized_connector
            ]

    def questions(self) -> list[str]:
        with self._lock:
            return sorted(
                {
                    market.question
                    for market in self._markets
                }
            )

    def status(self) -> dict[str, Any]:
        """
        Retorna informações do repositório.
        """

        with self._lock:
            return {
                "markets": len(
                    self._markets,
                ),
                "platforms": len(
                    {
                        market.platform
                        for market in self._markets
                    }
                ),
                "connectors": sorted(
                    {
                        market.connector
                        for market in self._markets
                    }
                ),
                "updated_at": (
                    self._updated_at.isoformat()
                    if self._updated_at
                    else None
                ),
            }


market_repository = MarketRepository()