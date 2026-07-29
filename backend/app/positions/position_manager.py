from app.positions.position_repository import position_repository


class PositionManager:

    def all(self):

        return position_repository.all()

    def open(self):

        return position_repository.open_positions()


position_manager = PositionManager()