class ReplayEngine:
    """
    Reproduz mercados históricos.
    """

    def __init__(self, dataframe):

        self.dataframe = dataframe

        self.index = 0

    def has_next(self):

        return self.index < len(self.dataframe)

    def next(self):

        row = self.dataframe.iloc[self.index]

        self.index += 1

        return row.to_dict()