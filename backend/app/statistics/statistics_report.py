from app.statistics.statistics_serializer import (
    statistics_serializer
)


class StatisticsReport:

    def create(self, statistics):

        return statistics_serializer.serialize(
            statistics
        )


statistics_report = StatisticsReport()