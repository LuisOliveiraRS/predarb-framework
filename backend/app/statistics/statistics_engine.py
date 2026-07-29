from app.statistics.statistics_calculator import (
    statistics_calculator
)

from app.statistics.statistics_repository import (
    statistics_repository
)

from app.statistics.statistics_report import (
    statistics_report
)


class StatisticsEngine:
    """
    Engine principal das estatísticas.
    """

    def update(self):

        statistics = (

            statistics_calculator.calculate()

        )

        statistics_repository.save(

            statistics

        )

        return statistics

    def summary(self):

        statistics = (

            statistics_repository.get()

        )

        if statistics is None:

            statistics = self.update()

        return statistics_report.create(

            statistics

        )


statistics_engine = StatisticsEngine()