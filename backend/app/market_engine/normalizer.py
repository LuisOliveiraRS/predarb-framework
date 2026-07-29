from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class MarketNormalizer:
    """Padroniza mercados legados e canônicos no mesmo contrato."""

    @staticmethod
    def _read(market: Mapping[str, Any], *names: str) -> Any:
        for name in names:
            if name in market and market[name] is not None:
                return market[name]
        return None

    def normalize(self, markets):
        normalized = []

        for market in markets:
            if not isinstance(market, Mapping):
                continue

            platform = str(self._read(market, "platform", "exchange") or "").strip().lower()
            question = str(self._read(market, "question", "title") or "").strip()
            yes_price = self._read(market, "yes_price", "yes")
            no_price = self._read(market, "no_price", "no")

            try:
                yes_value = float(yes_price)
                no_value = float(no_price)
            except (TypeError, ValueError):
                continue

            item = dict(market)
            item.update(
                {
                    "platform": platform,
                    "question": question,
                    "yes": yes_value,
                    "no": no_value,
                    "yes_price": yes_value,
                    "no_price": no_value,
                }
            )
            normalized.append(item)

        return normalized


market_normalizer = MarketNormalizer()
