from __future__ import annotations

from math import isfinite


class MarketValidator:
    """Remove mercados sem identificação ou preços válidos."""

    def validate(self, markets):
        valid = []

        for market in markets:
            question = str(market.get("question", "")).strip()
            platform = str(market.get("platform", "")).strip()

            try:
                yes_price = float(market.get("yes_price", market.get("yes")))
                no_price = float(market.get("no_price", market.get("no")))
            except (TypeError, ValueError):
                continue

            if not question or not platform:
                continue
            if not isfinite(yes_price) or not isfinite(no_price):
                continue
            if not (0 < yes_price <= 1 and 0 < no_price <= 1):
                continue

            valid.append(market)

        return valid


market_validator = MarketValidator()
