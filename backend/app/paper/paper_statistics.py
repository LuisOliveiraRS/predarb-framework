from __future__ import annotations

from typing import Any, Iterable, Mapping


class PaperStatistics:
    def report(
        self,
        history: Iterable[Any],
        *,
        account_snapshot: Mapping[str, Any] | None = None,
    ) -> dict[str, Any]:
        trades = list(history or [])
        volume = 0.0
        fees = 0.0
        for trade in trades:
            if hasattr(trade, "to_dict"):
                data = trade.to_dict()
            elif isinstance(trade, Mapping):
                data = trade
            else:
                data = vars(trade)
            quantity = float(data.get("quantity", 0) or 0)
            price = float(data.get("price", data.get("average_price", 0)) or 0)
            volume += float(data.get("gross_notional", quantity * price) or 0)
            fees += float(data.get("fee", data.get("fees_paid", 0)) or 0)
        result = {
            "trades": len(trades),
            "volume": round(volume, 8),
            "fees": round(fees, 8),
            "mode": "PAPER",
            "execution_authorized": False,
        }
        if account_snapshot:
            result.update(
                {
                    "equity": account_snapshot.get("equity"),
                    "realized_pnl": account_snapshot.get("realized_pnl"),
                    "unrealized_pnl": account_snapshot.get("unrealized_pnl"),
                    "total_pnl": account_snapshot.get("total_pnl"),
                }
            )
        return result


paper_statistics = PaperStatistics()
