from __future__ import annotations

from app.backtesting.simulation.slippage_simulator import slippage_simulator


class OrderSimulator:
    def execute(self, order, config):
        executed_price = slippage_simulator.apply(
            order.price,
            config.slippage,
        )

        return {
            "price": executed_price,
            "quantity": order.quantity,
            "commission": round(
                executed_price
                * order.quantity
                * config.commission,
                4,
            ),
        }


order_simulator = OrderSimulator()
