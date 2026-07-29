from datetime import timedelta


class ReplayClock:

    def __init__(self, start):

        self.current = start

    def tick(self, seconds=1):

        self.current += timedelta(seconds=seconds)

        return self.current