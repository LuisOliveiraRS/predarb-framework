"""Normalização de símbolos entre venues.

Cada venue nomeia o mesmo par de forma diferente: `BTCUSDT` na
Binance, `BTC-USDT` na OKX, `XBT/USD` na Kraken. Comparar preços
entre venues exige uma identidade canônica única.

A normalização é deliberadamente conservadora: um símbolo que não
possa ser decomposto com segurança levanta erro em vez de gerar um
palpite. Um par mal identificado produziria comparação entre
mercados diferentes, que é pior do que nenhuma comparação.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.crypto_arbitrage.domain.errors import (
    SymbolNormalizationError,
)


ASSET_ALIASES: dict[str, str] = {
    "XBT": "BTC",
    "XXBT": "BTC",
    "XETH": "ETH",
    "ZUSD": "USD",
    "ZEUR": "EUR",
}

SEPARATORS = ("/", "-", "_", ":")

QUOTE_ASSETS: tuple[str, ...] = (
    "USDT",
    "USDC",
    "BUSD",
    "FDUSD",
    "TUSD",
    "DAI",
    "USD",
    "EUR",
    "BRL",
    "BTC",
    "ETH",
    "BNB",
)


def normalize_asset(value: str) -> str:
    """Devolve o código canônico de um ativo."""

    normalized = str(value or "").strip().upper()

    if not normalized:
        raise SymbolNormalizationError(
            "Ativo não pode ser vazio."
        )

    if not normalized.isalnum():
        raise SymbolNormalizationError(
            f"Ativo com caracteres inválidos: {value!r}."
        )

    return ASSET_ALIASES.get(normalized, normalized)


@dataclass(frozen=True, slots=True)
class SymbolPair:
    """Par canônico, independente da venue."""

    base_asset: str
    quote_asset: str

    def __post_init__(self) -> None:
        if self.base_asset == self.quote_asset:
            raise SymbolNormalizationError(
                "Base e quote não podem ser o mesmo ativo."
            )

    @property
    def canonical(self) -> str:
        return f"{self.base_asset}/{self.quote_asset}"

    def to_dict(self) -> dict[str, Any]:
        return {
            "base_asset": self.base_asset,
            "quote_asset": self.quote_asset,
            "canonical": self.canonical,
        }

    def __str__(self) -> str:
        return self.canonical


def build_pair(
    base_asset: str,
    quote_asset: str,
) -> SymbolPair:
    return SymbolPair(
        base_asset=normalize_asset(base_asset),
        quote_asset=normalize_asset(quote_asset),
    )


def parse_symbol(raw_symbol: str) -> SymbolPair:
    """Interpreta o símbolo de uma venue como par canônico.

    Aceita separadores explícitos (`BTC/USDT`, `BTC-USDT`) e a
    forma concatenada (`BTCUSDT`), esta última resolvida apenas
    quando termina num quote asset conhecido.
    """

    normalized = str(raw_symbol or "").strip().upper()

    if not normalized:
        raise SymbolNormalizationError(
            "Símbolo não pode ser vazio."
        )

    for separator in SEPARATORS:
        if separator in normalized:
            parts = [
                part
                for part in normalized.split(separator)
                if part
            ]

            if len(parts) != 2:
                raise SymbolNormalizationError(
                    f"Símbolo ambíguo: {raw_symbol!r}."
                )

            return build_pair(parts[0], parts[1])

    return _split_concatenated(normalized, raw_symbol)


def _split_concatenated(
    normalized: str,
    raw_symbol: str,
) -> SymbolPair:
    """Separa `BTCUSDT` usando a lista de quotes conhecidos.

    Percorre do quote mais longo para o mais curto para que
    `BTCUSDT` resolva em `USDT` e não em `USD` com base `BTCUST`.
    """

    candidates = sorted(
        QUOTE_ASSETS,
        key=len,
        reverse=True,
    )

    for quote in candidates:
        if not normalized.endswith(quote):
            continue

        base = normalized[: -len(quote)]

        if not base:
            continue

        return build_pair(base, quote)

    raise SymbolNormalizationError(
        f"Não foi possível separar base e quote em "
        f"{raw_symbol!r}. Informe base e quote "
        "explicitamente."
    )
