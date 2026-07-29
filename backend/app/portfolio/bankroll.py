class Bankroll:

    def __init__(self):

        self.initial = 10000.0

        self.available = 10000.0

        self.locked = 0.0

    def allocate(self, amount):

        if amount > self.available:

            return False

        self.available -= amount

        self.locked += amount

        return True

    def release(self, amount):

        self.locked -= amount

        self.available += amount

    @property
    def utilization(self):

        return self.locked / self.initial


bankroll = Bankroll()