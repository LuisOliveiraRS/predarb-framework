class MarketDeduplicator:

    """
    Remove mercados duplicados.
    """

    def process(self, markets):

        unique = {}

        for market in markets:

            key = (

                market["platform"],

                market["question"]

            )

            unique[key] = market

        return list(unique.values())


market_deduplicator = MarketDeduplicator()