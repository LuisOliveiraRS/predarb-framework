from app.positions.position_status import PositionStatus


class PositionMonitor:
    """
    Monitora posições abertas.
    """

    def update(self, positions):

        updated = []

        for position in positions:

            if position.status == PositionStatus.OPEN:

                position.status = PositionStatus.MONITORING

            updated.append(position)

        return updated


position_monitor = PositionMonitor()