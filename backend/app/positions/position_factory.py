from app.positions.position import Position
from app.positions.position_manager import position_manager


class PositionFactory:

    def create(
        self,
        opportunity,
        executed_orders
    ):

        position = Position(

            platform="MULTI",

            question=opportunity["question"],

            side="ARBITRAGE",

            quantity=1,

            average_price=(
                opportunity["yes_price"] +
                opportunity["no_price"]
            ) / 2

        )

        position.pnl = 0

        position.roi = 0

        position.orders = executed_orders

        position_manager.add(position)

        return position


position_factory = PositionFactory()