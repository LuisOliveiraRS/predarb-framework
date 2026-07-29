class MarketStatistics:

    def summary(self, markets):

        return {

            "markets": len(markets),

            "platforms":

                len(

                    {

                        market["platform"]

                        for market in markets

                    }

                )

        }


statistics = MarketStatistics()