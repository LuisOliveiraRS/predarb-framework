class StatisticsRepository:
    """
    Armazena o último snapshot das estatísticas.
    """

    def __init__(self):

        self.statistics = None

    def save(self, statistics):

        self.statistics = statistics

    def get(self):

        return self.statistics


statistics_repository = StatisticsRepository()