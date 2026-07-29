from dataclasses import asdict


class StatisticsSerializer:

    def serialize(self, statistics):

        return asdict(statistics)


statistics_serializer = StatisticsSerializer()