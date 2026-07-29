from __future__ import annotations

from app.orders.order_status import OrderStatus
from app.paper.paper_account import paper_account
from app.utils.time import utc_now


class PaperOrderExecutor:
    """Executor paper explícito; nunca encaminha ordens a connectors live."""

    def execute(self, order):
        order.status = OrderStatus.FILLED
        order.executed_at = utc_now()
        order.filled_quantity = order.quantity
        order.average_price = order.price
        report = {
            "order_id": order.id,
            "platform": getattr(order, "platform", ""),
            "symbol": getattr(order, "symbol", ""),
            "leg": getattr(order, "leg", ""),
            "side": getattr(getattr(order, "side", "BUY"), "value", getattr(order, "side", "BUY")),
            "status": "FILLED",
            "requested_price": order.price,
            "average_price": order.price,
            "requested_quantity": order.quantity,
            "filled_quantity": order.quantity,
            "gross_notional": order.quantity * order.price,
            "fee": 0.0,
            "net_notional": order.quantity * order.price,
            "slippage_rate": 0.0,
            "mode": "PAPER",
            "executed_at": order.executed_at.isoformat(),
        }
        paper_account.commit_execution([order], [report], persist=False)
        return order


paper_order_executor = PaperOrderExecutor()
