from __future__ import annotations

from collections.abc import Mapping, Sequence
from copy import deepcopy
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.settings import settings
from app.paper.paper_equity_tracker import PaperEquityTracker, paper_equity_tracker
from app.paper.paper_models import PaperTrade, number, text, utc_iso
from app.paper.paper_position_manager import (
    PaperPositionManager,
    paper_position_manager,
)
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_trade_history import PaperTradeHistory, paper_trade_history
from app.paper.paper_wallet import PaperWallet, paper_wallet


class PaperAccount:
    """Conta paper explícita e isolada de OMS, connectors e execução live."""

    STATE_VERSION = 2
    COMPATIBLE_STATE_VERSIONS = {1, 2}

    def __init__(
        self,
        *,
        initial_balance: float = 10_000.0,
        wallet: PaperWallet | None = None,
        history: PaperTradeHistory | None = None,
        positions: PaperPositionManager | None = None,
        equity_tracker: PaperEquityTracker | None = None,
        repository: PaperAccountRepository | None = None,
        auto_persist: bool = True,
    ) -> None:
        self._lock = RLock()
        self.account_id = str(uuid4())
        self.created_at = utc_iso()
        self.updated_at = self.created_at
        self.wallet = wallet or PaperWallet(initial_balance)
        self.history = history or PaperTradeHistory()
        self.positions = positions or PaperPositionManager()
        self.equity_tracker = equity_tracker or PaperEquityTracker()
        self.repository = repository
        self.auto_persist = bool(auto_persist)
        self._processed_order_ids: set[str] = set()
        self._dirty = False
        self._last_persisted_at: str | None = None
        self._record_equity_locked("INITIAL", force=True)

    def _equity_payload_locked(self) -> dict[str, Any]:
        all_positions = self.positions.all(include_closed=True)
        open_positions = [item for item in all_positions if item.open]
        realized = sum(item.realized_pnl for item in all_positions)
        unrealized = sum(item.unrealized_pnl for item in open_positions)
        market_value = sum(item.market_value for item in open_positions)
        wallet = self.wallet.snapshot()
        cash = float(wallet.get("balance", wallet.get("cash", 0.0)) or 0.0)
        equity = cash + market_value
        initial = float(wallet.get("initial_balance", 0.0) or 0.0)
        return {
            "updated_at": self.updated_at,
            "wallet": wallet,
            "open_positions": len(open_positions),
            "trade_count": self.history.count(),
            "market_value": round(market_value, 8),
            "equity": round(equity, 8),
            "realized_pnl": round(realized, 8),
            "unrealized_pnl": round(unrealized, 8),
            "total_pnl": round(equity - initial, 8),
            "return_rate": round((equity - initial) / initial, 8) if initial else 0.0,
        }

    def _record_equity_locked(self, reason: str, *, force: bool = False) -> dict[str, Any]:
        point = self.equity_tracker.record(
            self._equity_payload_locked(),
            reason=reason,
            timestamp=self.updated_at,
            force=force,
        )
        return point.to_dict()

    @staticmethod
    def _read(target: Any, name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(name, default)
        return getattr(target, name, default)

    def _trade_from(
        self,
        order: Any,
        report: Mapping[str, Any],
        *,
        execution_id: str,
    ) -> PaperTrade:
        order_id = text(report.get("order_id") or self._read(order, "id"))
        if not order_id:
            raise ValueError("Relatório paper sem order_id.")
        mode = text(report.get("mode"), "PAPER").upper()
        status = text(report.get("status")).upper()
        if mode != "PAPER" or status != "FILLED":
            raise ValueError("Somente relatórios PAPER/FILLED podem ser persistidos.")
        raw_side = report.get("side") or self._read(order, "side", "BUY")
        side = text(getattr(raw_side, "value", raw_side)).upper()
        if "." in side:
            side = side.rsplit(".", 1)[-1]
        quantity = number(
            report.get("filled_quantity", self._read(order, "quantity")),
            "filled_quantity",
            minimum=0.0,
        )
        price = number(
            report.get("average_price", self._read(order, "price")),
            "average_price",
            minimum=0.0,
        )
        fee = number(report.get("fee", 0.0), "fee", minimum=0.0)
        gross = number(
            report.get("gross_notional", quantity * price),
            "gross_notional",
            minimum=0.0,
        )
        cash_flow = -(gross + fee) if side == "BUY" else gross - fee
        return PaperTrade(
            execution_id=execution_id,
            order_id=order_id,
            opportunity_id=text(self._read(order, "opportunity_id")),
            platform=text(report.get("platform") or self._read(order, "platform")),
            symbol=text(report.get("symbol") or self._read(order, "symbol")),
            market=text(self._read(order, "market") or report.get("symbol")),
            leg=text(report.get("leg") or self._read(order, "leg")).upper(),
            side=side,
            quantity=quantity,
            price=price,
            fee=fee,
            gross_notional=gross,
            cash_flow=cash_flow,
            executed_at=text(report.get("executed_at")) or utc_iso(),
            metadata={
                "paper_report": deepcopy(dict(report)),
                "source": "PaperAccount.commit_execution",
            },
        )

    def commit_execution(
        self,
        orders: Sequence[Any],
        reports: Sequence[Mapping[str, Any]],
        *,
        execution_id: str | None = None,
        persist: bool | None = None,
    ) -> dict[str, Any]:
        resolved_orders = list(orders or [])
        resolved_reports = list(reports or [])
        if not resolved_reports:
            raise ValueError("Nenhum relatório paper foi informado.")
        order_map = {
            text(self._read(order, "id")): order
            for order in resolved_orders
            if text(self._read(order, "id"))
        }
        resolved_execution_id = text(execution_id) or str(uuid4())
        trades: list[PaperTrade] = []
        for report in resolved_reports:
            report_order_id = text(report.get("order_id"))
            order = order_map.get(report_order_id)
            if order is None:
                raise ValueError(
                    f"Não foi encontrada a ordem do relatório: {report_order_id}"
                )
            trades.append(
                self._trade_from(
                    order,
                    report,
                    execution_id=resolved_execution_id,
                )
            )
        trade_order_ids = [trade.order_id for trade in trades]
        if len(trade_order_ids) != len(set(trade_order_ids)):
            raise ValueError("A execução paper contém order_id duplicado.")

        with self._lock:
            duplicates = set(trade_order_ids).intersection(self._processed_order_ids)
            if duplicates:
                raise ValueError(
                    "Ordens paper já processadas: " + ", ".join(sorted(duplicates))
                )
            required_cash = sum(
                -trade.cash_flow for trade in trades if trade.cash_flow < 0
            )
            if required_cash > self.wallet.available() + 1e-9:
                raise ValueError("Saldo paper insuficiente para confirmar a execução.")

            backup = self.export_state()
            backup_dirty = self._dirty
            backup_persisted_at = self._last_persisted_at
            try:
                committed: list[dict[str, Any]] = []
                for trade in trades:
                    if trade.cash_flow < 0:
                        self.wallet.withdraw(-trade.cash_flow)
                    else:
                        self.wallet.deposit(trade.cash_flow)
                    position = self.positions.apply_trade(trade)
                    stored = self.history.add(trade)
                    self._processed_order_ids.add(trade.order_id)
                    committed.append(
                        {
                            "trade": stored.to_dict(),
                            "position": position.to_dict(),
                        }
                    )
                self.updated_at = utc_iso()
                self._dirty = True
                self._record_equity_locked("EXECUTION")
            except Exception:
                self.restore_state(backup)
                self._dirty = backup_dirty
                self._last_persisted_at = backup_persisted_at
                raise

        should_persist = self.auto_persist if persist is None else bool(persist)
        if should_persist and self.repository is not None:
            self.save()

        return {
            "status": "COMMITTED",
            "mode": "PAPER",
            "execution_id": resolved_execution_id,
            "orders_committed": len(trades),
            "trades": committed,
            "account": self.snapshot(include_trades=False),
            "execution_authorized": False,
            "live_execution": False,
        }

    def mark_to_market(
        self,
        prices: Mapping[str, Any],
        *,
        persist: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(prices, Mapping):
            raise TypeError("prices deve ser um mapeamento posição/preço.")
        updated: list[dict[str, Any]] = []
        with self._lock:
            for identifier, price in prices.items():
                position = self.positions.mark(str(identifier), price)
                updated.append(position.to_dict())
            if updated:
                self.updated_at = utc_iso()
                self._dirty = True
                self._record_equity_locked("MARK_TO_MARKET")
        if persist and self.repository is not None:
            self.save()
        return {
            "status": "MARKED",
            "positions_updated": len(updated),
            "positions": updated,
            "account": self.snapshot(include_trades=False),
        }

    def settle(
        self,
        position_id: str,
        settlement_price: Any,
        *,
        fee_rate: float = 0.0,
        persist: bool | None = None,
    ) -> dict[str, Any]:
        position = self.positions.require(position_id)
        if not position.open:
            raise ValueError("A posição paper já está encerrada.")
        price = number(settlement_price, "settlement_price", minimum=0.0)
        if price > 1:
            raise ValueError("settlement_price deve estar entre 0 e 1.")
        rate = number(fee_rate, "fee_rate", minimum=0.0)
        fee = position.quantity * price * rate
        order_id = f"paper-settlement:{uuid4()}"
        trade = PaperTrade(
            execution_id=f"settlement:{uuid4()}",
            order_id=order_id,
            platform=position.platform,
            symbol=position.symbol,
            market=position.market,
            leg=position.leg,
            side="SELL",
            quantity=position.quantity,
            price=price,
            fee=fee,
            gross_notional=position.quantity * price,
            cash_flow=position.quantity * price - fee,
            metadata={"settlement": True},
        )
        with self._lock:
            backup = self.export_state()
            backup_dirty = self._dirty
            backup_persisted_at = self._last_persisted_at
            try:
                self.wallet.deposit(trade.cash_flow)
                updated_position = self.positions.apply_trade(trade)
                stored = self.history.add(trade)
                self._processed_order_ids.add(order_id)
                self.updated_at = utc_iso()
                self._dirty = True
                self._record_equity_locked("SETTLEMENT")
            except Exception:
                self.restore_state(backup)
                self._dirty = backup_dirty
                self._last_persisted_at = backup_persisted_at
                raise
        should_persist = self.auto_persist if persist is None else bool(persist)
        if should_persist and self.repository is not None:
            self.save()
        return {
            "status": "SETTLED",
            "mode": "PAPER",
            "trade": stored.to_dict(),
            "position": updated_position.to_dict(),
            "account": self.snapshot(include_trades=False),
            "execution_authorized": False,
        }

    def export_state(self) -> dict[str, Any]:
        with self._lock:
            return {
                "state_version": self.STATE_VERSION,
                "account_id": self.account_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "wallet": self.wallet.snapshot(),
                "positions": self.positions.snapshot(include_closed=True),
                "trades": self.history.snapshot(),
                "processed_order_ids": sorted(self._processed_order_ids),
                "equity_curve": self.equity_tracker.snapshot(),
            }

    def restore_state(self, state: Mapping[str, Any]) -> None:
        version = int(state.get("state_version", 1))
        if version not in self.COMPATIBLE_STATE_VERSIONS:
            raise ValueError("Versão incompatível do estado da conta paper.")
        wallet = state.get("wallet", {})
        positions = state.get("positions", [])
        trades = state.get("trades", [])
        equity_curve = state.get("equity_curve", [])
        processed = {
            text(value)
            for value in state.get("processed_order_ids", [])
            if text(value)
        }
        with self._lock:
            self.wallet.restore(wallet)
            self.positions.restore(positions)
            self.history.restore(trades)
            history_ids = {
                trade.order_id for trade in self.history.all() if trade.order_id
            }
            if not history_ids.issubset(processed):
                processed.update(history_ids)
            self._processed_order_ids = processed
            self.account_id = text(state.get("account_id")) or str(uuid4())
            self.created_at = text(state.get("created_at")) or utc_iso()
            self.updated_at = text(state.get("updated_at")) or self.created_at
            self.equity_tracker.restore(equity_curve)
            if not self.equity_tracker.snapshot():
                self._record_equity_locked("RESTORE", force=True)
            self._dirty = False

    def save(self) -> str:
        if self.repository is None:
            raise RuntimeError("A conta paper não possui repositório configurado.")
        path = self.repository.save(self.export_state())
        with self._lock:
            self._dirty = False
            self._last_persisted_at = utc_iso()
        return str(path)

    def load(self) -> bool:
        if self.repository is None:
            raise RuntimeError("A conta paper não possui repositório configurado.")
        state = self.repository.load()
        if state is None:
            return False
        self.restore_state(state)
        with self._lock:
            self._last_persisted_at = utc_iso()
        return True

    def reset(
        self,
        *,
        initial_balance: float | None = None,
        persist: bool = False,
    ) -> dict[str, Any]:
        with self._lock:
            self.wallet.reset(initial_balance)
            self.positions.clear()
            self.history.clear()
            self._processed_order_ids.clear()
            self.equity_tracker.clear()
            self.account_id = str(uuid4())
            self.created_at = utc_iso()
            self.updated_at = self.created_at
            self._dirty = True
            self._record_equity_locked("RESET", force=True)
        if persist and self.repository is not None:
            self.save()
        return self.snapshot()

    def snapshot(self, *, include_trades: bool = True) -> dict[str, Any]:
        with self._lock:
            all_positions = self.positions.all(include_closed=True)
            open_positions = [item for item in all_positions if item.open]
            closed_positions = [item for item in all_positions if not item.open]
            metrics = self._equity_payload_locked()
            result: dict[str, Any] = {
                "status": "READY",
                "mode": "PAPER",
                "account_id": self.account_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "wallet": self.wallet.snapshot(),
                "positions": [item.to_dict() for item in all_positions],
                "open_positions": len(open_positions),
                "closed_positions": len(closed_positions),
                "trade_count": self.history.count(),
                "market_value": metrics["market_value"],
                "equity": metrics["equity"],
                "realized_pnl": metrics["realized_pnl"],
                "unrealized_pnl": metrics["unrealized_pnl"],
                "total_pnl": metrics["total_pnl"],
                "return_rate": metrics["return_rate"],
                "equity_curve": self.equity_tracker.snapshot(),
                "equity_analytics": self.equity_tracker.analytics(),
                "processed_orders": len(self._processed_order_ids),
                "dirty": self._dirty,
                "last_persisted_at": self._last_persisted_at,
                "repository": self.repository.status() if self.repository else None,
                "advisory_only": False,
                "execution_authorized": False,
                "live_execution": False,
            }
            if include_trades:
                result["trades"] = self.history.dictionaries()
            return deepcopy(result)

    def status(self) -> dict[str, Any]:
        snapshot = self.snapshot(include_trades=False)
        return {
            key: snapshot[key]
            for key in (
                "status",
                "mode",
                "account_id",
                "open_positions",
                "closed_positions",
                "trade_count",
                "equity",
                "total_pnl",
                "dirty",
                "execution_authorized",
                "live_execution",
            )
        }


paper_account = PaperAccount(
    initial_balance=settings.PAPER_INITIAL_BALANCE,
    wallet=paper_wallet,
    history=paper_trade_history,
    positions=paper_position_manager,
    equity_tracker=paper_equity_tracker,
    repository=PaperAccountRepository(settings.PAPER_ACCOUNT_PATH),
    auto_persist=False,
)
