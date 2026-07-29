class OpportunityHistory:

    def __init__(self):

        self.history = []

    def save(self, opportunity):

        self.history.append(opportunity)

    def all(self):

        return self.history


history_repository = OpportunityHistory()