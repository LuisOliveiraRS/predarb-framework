from __future__ import annotations

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.dashboard.cache import DashboardCache
from app.dashboard.dashboard_service import DashboardService, DashboardSources
from app.dashboard.dashboard_state import DashboardState
from app.execution.execution_engine import ExecutionEngine
from app.paper.paper_account import PaperAccount
from app.paper.paper_equity_tracker import PaperEquityTracker
from app.paper.paper_position_manager import PaperPositionManager
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_trade_history import PaperTradeHistory
from app.paper.paper_wallet import PaperWallet

REPORT_PATH = BACKEND_ROOT / "real_test_reports" / "phase6_paper_dashboard_session_report.json"


class Audit:
    def __init__(self) -> None:
        self.checks: list[dict[str, Any]] = []
        self.failures = 0

    def check(self, name: str, condition: bool, details: Any = None) -> None:
        status = "PASS" if condition else "FAIL"
        print(f"[{status}] {name}")
        self.checks.append({"name": name, "status": status, "details": details})
        if not condition:
            self.failures += 1

    def finish(self, extra: dict[str, Any] | None = None) -> int:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        report = {
            "phase": 6,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "summary": {
                "passed": len(self.checks) - self.failures,
                "failed": self.failures,
                "checks": len(self.checks),
            },
            "checks": self.checks,
            "details": extra or {},
        }
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print()
        print(f"Aprovados: {report['summary']['passed']}")
        print(f"Falhas:    {report['summary']['failed']}")
        print(f"Relatório: {REPORT_PATH}")
        return 1 if self.failures else 0


def build_account(path: Path) -> PaperAccount:
    return PaperAccount(
        initial_balance=10_000,
        wallet=PaperWallet(10_000),
        history=PaperTradeHistory(),
        positions=PaperPositionManager(),
        equity_tracker=PaperEquityTracker(max_points=500),
        repository=PaperAccountRepository(path),
        auto_persist=False,
    )


def order_and_report(cycle: int, price: float) -> tuple[dict[str, Any], dict[str, Any]]:
    order_id = f"phase6-order-{cycle:03d}"
    symbol = f"PHASE6-{cycle:03d}"
    quantity = 20 + cycle
    fee = round(quantity * price * 0.001, 8)
    order = {
        "id": order_id,
        "opportunity_id": f"phase6-opportunity-{cycle:03d}",
        "platform": "paper-simulator",
        "symbol": symbol,
        "market": f"Sessão Paper {cycle:03d}",
        "leg": "YES" if cycle % 2 else "NO",
        "side": "BUY",
        "quantity": quantity,
        "price": price,
    }
    report = {
        "order_id": order_id,
        "status": "FILLED",
        "mode": "PAPER",
        "platform": "paper-simulator",
        "symbol": symbol,
        "leg": order["leg"],
        "side": "BUY",
        "filled_quantity": quantity,
        "average_price": price,
        "gross_notional": round(quantity * price, 8),
        "fee": fee,
        "executed_at": datetime.now(timezone.utc).isoformat(),
    }
    return order, report


def main() -> int:
    audit = Audit()
    executor_calls: list[Any] = []

    with TemporaryDirectory() as directory:
        state_path = Path(directory) / "paper-account.json"
        account = build_account(state_path)
        account.reset(initial_balance=10_000, persist=False)

        cycles = 24
        for cycle in range(1, cycles + 1):
            entry_price = round(0.28 + (cycle % 7) * 0.045, 4)
            order, report = order_and_report(cycle, entry_price)
            account.commit_execution([order], [report], persist=False)

            marks: dict[str, float] = {}
            for index, position in enumerate(account.positions.open_positions()):
                wave = math.sin((cycle + index) / 2.8) * 0.08
                mark = min(0.95, max(0.05, position.average_price + wave))
                marks[position.id] = round(mark, 4)
            account.mark_to_market(marks, persist=False)

            if cycle % 4 == 0:
                oldest = account.positions.open_positions()[0]
                settlement = 1.0 if cycle % 8 == 0 else 0.0
                account.settle(oldest.id, settlement, fee_rate=0.001, persist=False)

            account.save()

        snapshot = account.snapshot(include_trades=True)
        curve = snapshot["equity_curve"]
        analytics = snapshot["equity_analytics"]

        audit.check(
            "Sessão prolongada concluída",
            snapshot["trade_count"] >= cycles,
            {"cycles": cycles, "trades": snapshot["trade_count"]},
        )
        audit.check(
            "Curva de equity registrada",
            len(curve) >= cycles * 2,
            {"points": len(curve)},
        )
        audit.check(
            "Analytics da curva consistentes",
            analytics["points"] == len(curve)
            and analytics["current_equity"] == snapshot["equity"]
            and analytics["max_drawdown"] >= 0
            and 0 <= analytics["max_drawdown_rate"] <= 1,
            analytics,
        )
        audit.check(
            "Persistência JSON criada",
            state_path.is_file() and state_path.stat().st_size > 0,
            {"path": str(state_path), "bytes": state_path.stat().st_size},
        )

        restored = build_account(state_path)
        loaded = restored.load()
        restored_snapshot = restored.snapshot(include_trades=True)
        audit.check(
            "Restart preservou conta e curva",
            loaded
            and restored_snapshot["account_id"] == snapshot["account_id"]
            and restored_snapshot["trade_count"] == snapshot["trade_count"]
            and restored_snapshot["equity_curve"] == curve
            and restored_snapshot["equity"] == snapshot["equity"],
            {
                "loaded": loaded,
                "trades": restored_snapshot["trade_count"],
                "points": len(restored_snapshot["equity_curve"]),
            },
        )

        service = DashboardService(
            state=DashboardState(),
            cache=DashboardCache(),
            sources=DashboardSources(
                markets=lambda: [],
                orders=lambda: [],
                positions=lambda: [],
                trades=lambda: [],
                portfolio=lambda: {},
                statistics=lambda: {},
                router=lambda: {},
                paper=lambda: {**restored_snapshot, "enabled": True},
                notifications=lambda: [],
            ),
        )
        dashboard = service.snapshot()
        paper = dashboard["data"]["paper"]
        audit.check(
            "Dashboard recebeu a conta Paper",
            paper["equity"] == restored_snapshot["equity"]
            and paper["trade_count"] == restored_snapshot["trade_count"]
            and len(paper["equity_curve"]) == len(curve),
            {
                "equity": paper["equity"],
                "trades": paper["trade_count"],
                "curve_points": len(paper["equity_curve"]),
            },
        )
        audit.check(
            "Diagnóstico Paper consistente",
            dashboard["diagnostics"]["sources"]["paper_positions"]
            == len(restored_snapshot["positions"])
            and dashboard["diagnostics"]["sources"]["paper_trades"]
            == restored_snapshot["trade_count"],
            dashboard["diagnostics"]["sources"],
        )

        live_engine = ExecutionEngine(
            executor=lambda order: executor_calls.append(order) or {"accepted": True}
        )
        disabled_report = live_engine.execute({"id": "phase6-live-guard"})
        audit.check(
            "Execução live permaneceu bloqueada",
            disabled_report["status"] == "DISABLED"
            and disabled_report["executed"] is False
            and not executor_calls
            and restored_snapshot["execution_authorized"] is False
            and restored_snapshot["live_execution"] is False,
            disabled_report,
        )

        return audit.finish(
            {
                "cycles": cycles,
                "final_account": restored_snapshot,
                "dashboard_paper": paper,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
