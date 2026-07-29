class PositionRepository:

    def __init__(self):

        self.positions = []

    def add(self, position):

        self.positions.append(position)

    def all(self):

        return self.positions

    def open_positions(self):

        return [

            p

            for p in self.positions

            if p.status == "OPEN"

        ]

    def count(self):

        return len(self.positions)


position_repository = PositionRepository()