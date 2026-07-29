from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any


_MISSING = object()


class LiquidityService:
    """
    Valida a liquidez disponível para uma
    oportunidade de arbitragem.

    A liquidez pode estar:

    - diretamente em opportunity["liquidity"];
    - em market_yes["liquidity"];
    - em market_no["liquidity"].

    Quando existirem valores nos dois mercados,
    será utilizada a menor liquidez, pois ela
    representa o lado limitante da execução.
    """

    MIN_LIQUIDITY = 100.0

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = _MISSING,
    ) -> Any:
        """
        Recupera campos de dicionários ou objetos.
        """

        if isinstance(
            target,
            Mapping,
        ):
            if field_name in target:
                return target[field_name]

        elif target is not None and hasattr(
            target,
            field_name,
        ):
            return getattr(
                target,
                field_name,
            )

        if default is not _MISSING:
            return default

        raise ValueError(
            f"Campo {field_name!r} não encontrado."
        )

    @staticmethod
    def _to_number(
        value: Any,
    ) -> float | None:
        """
        Converte liquidez para número.
        """

        if value is None or isinstance(
            value,
            bool,
        ):
            return None

        try:
            return float(value)

        except (TypeError, ValueError):
            return None

    def get_liquidity(
        self,
        opportunity: Any,
    ) -> float | None:
        """
        Recupera a liquidez efetiva da oportunidade.
        """

        direct_liquidity = self._to_number(
            self._read_field(
                opportunity,
                "liquidity",
                None,
            )
        )

        if direct_liquidity is not None:
            return direct_liquidity

        market_yes = self._read_field(
            opportunity,
            "market_yes",
            None,
        )

        market_no = self._read_field(
            opportunity,
            "market_no",
            None,
        )

        yes_liquidity = self._to_number(
            self._read_field(
                market_yes,
                "liquidity",
                None,
            )
        )

        no_liquidity = self._to_number(
            self._read_field(
                market_no,
                "liquidity",
                None,
            )
        )

        available = [
            value
            for value in (
                yes_liquidity,
                no_liquidity,
            )
            if value is not None
        ]

        if not available:
            return None

        return min(available)

    def is_liquid(
        self,
        opportunity: Any,
        *,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
    ) -> bool:
        """
        Verifica se uma oportunidade possui
        liquidez suficiente.

        Por compatibilidade, uma oportunidade sem
        campo de liquidez continua aprovada quando
        ``require_liquidity`` for False.
        """

        if opportunity is None:
            return False

        minimum = (
            self.MIN_LIQUIDITY
            if min_liquidity is None
            else float(min_liquidity)
        )

        liquidity = self.get_liquidity(
            opportunity,
        )

        if liquidity is None:
            return not require_liquidity

        return liquidity >= minimum

    def validate(
        self,
        opportunities: Iterable[Any] | None,
        *,
        min_liquidity: float | None = None,
        require_liquidity: bool = False,
    ) -> list[Any]:
        """
        Retorna somente oportunidades com
        liquidez suficiente.
        """

        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "Opportunities deve ser uma coleção."
            )

        return [
            opportunity
            for opportunity in opportunities
            if self.is_liquid(
                opportunity,
                min_liquidity=min_liquidity,
                require_liquidity=require_liquidity,
            )
        ]


liquidity_service = LiquidityService()