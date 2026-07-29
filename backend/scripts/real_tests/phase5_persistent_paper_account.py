from __future__ import annotations

import json
import os
import sys
import traceback
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable
from uuid import uuid4

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

TEST_ACCOUNT_PATH = BACKEND_ROOT / "paper_data" / "phase5_test_account.json"
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "true",
        "HYPERLIQUID_CONNECTOR_ENABLED": "false",
        "INITIAL_MARKET_SYNC_ENABLED": "false",
        "SCHEDULER_ENABLED": "false",
        "EXECUTION_WORKER_ENABLED": "false",
        "ROUTER_DASHBOARD_ENABLED": "false",
        "AI_ADVISORY_ONLY": "true",
        "AI_EXECUTION_AUTHORIZED": "false",
        "AI_AUTO_LOAD_MODEL": "false",
        "PAPER_ACCOUNT_ENABLED": "true",
        "PAPER_ACCOUNT_AUTO_LOAD": "true",
        "PAPER_ACCOUNT_AUTO_SAVE": "true",
        "PAPER_ACCOUNT_PATH": str(TEST_ACCOUNT_PATH),
        "PAPER_INITIAL_BALANCE": "10000",
        "DATABASE_URL": "sqlite:///predarb_real_test_phase5.db",
    }
)

from fastapi.testclient import TestClient

from app.core.application import create_app
from app.execution.execution_engine import ExecutionEngine
from app.orders.fill_repository import fill_repository
from app.orders.order import Order
from app.orders.order_repository import order_repository
from app.paper import PaperAccount, PaperAccountRepository
from app.paper.paper_runtime import paper_account_runtime
from app.pipeline.pipeline import Pipeline
from app.pipeline.pipeline_context import PipelineContext
from app.pipeline.stages.paper_account_stage import PaperAccountStage
from app.pipeline.stages.paper_stage import PaperStage
from app.positions.position_repository import position_repository
from app.trading.trade_repository import trade_repository

REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase5_persistent_paper_account_report.json"


class Report:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.checks: list[dict[str, Any]] = []

    def run(self, name: str, operation: Callable[[], Any]) -> Any:
        try:
            details = operation()
            self.checks.append({"name": name, "status": "PASS", "details": plain(details)})
            print(f"[PASS] {name}")
            return details
        except Exception as exc:
            self.checks.append(
                {
                    "name": name,
                    "status": "FAIL",
                    "error": str(exc),
                    "traceback": traceback.format_exc(),
                }
            )
            print(f"[FAIL] {name}: {exc}")
            return None

    def finish(self) -> dict[str, Any]:
        finished_at = datetime.now(timezone.utc)
        passed = sum(item["status"] == "PASS" for item in self.checks)
        failed = sum(item["status"] == "FAIL" for item in self.checks)
        return {
            "test": "PredArb Phase 5 - Persistent Paper Account",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round((finished_at - self.started_at).total_seconds(), 3),
            "summary": {"passed": passed, "failed": failed, "total": len(self.checks)},
            "checks": self.checks,
        }


def plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [plain(item) for item in value]
    if hasattr(value, "to_dict"):
        return plain(value.to_dict())
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    return str(value)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def repositories() -> dict[str, int]:
    return {
        "orders": order_repository.count(),
        "fills": fill_repository.count(),
        "trades": trade_repository.count(),
        "positions": len(list(position_repository.all() or [])),
    }


def make_orders(prefix: str = "phase5") -> list[Order]:
    return [
        Order(
            id=f"{prefix}-yes-{uuid4()}",
            platform="Hyperliquid",
            market="Phase 5 Test Event",
            symbol="PHASE5",
            side="BUY",
            quantity=100,
            price=0.44,
            opportunity_id=f"{prefix}-opportunity",
            leg="YES",
            mode="PAPER",
        ),
        Order(
            id=f"{prefix}-no-{uuid4()}",
            platform="Phase5Control",
            market="Phase 5 Test Event",
            symbol="PHASE5",
            side="BUY",
            quantity=100,
            price=0.46,
            opportunity_id=f"{prefix}-opportunity",
            leg="NO",
            mode="PAPER",
        ),
    ]


def simulate(orders: list[Order], *, fee_rate: float = 0.001) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    context = PipelineContext({"orders": orders})
    PaperStage(fee_rate=fee_rate, strict=True).process(context)
    return context.execution_report, list(context.execution_reports or [])


def main() -> int:
    report = Report()
    shared: dict[str, Any] = {}
    TEST_ACCOUNT_PATH.unlink(missing_ok=True)

    def check_core_pipeline() -> dict[str, Any]:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "account.json"
            account = PaperAccount(
                initial_balance=10_000,
                repository=PaperAccountRepository(path),
                auto_persist=False,
            )
            orders = make_orders("core")
            pipeline = Pipeline(
                [
                    PaperStage(fee_rate=0.001, strict=True),
                    PaperAccountStage(account=account, persist=True),
                ],
                name="paper-persistent",
            )
            result = pipeline.execute(PipelineContext({"orders": orders}))
            require(result.success, f"Pipeline falhou: {result.errors}")
            snapshot = account.snapshot()
            require(snapshot["trade_count"] == 2, "A conta não registrou duas negociações.")
            require(snapshot["open_positions"] == 2, "A conta não abriu duas posições.")
            require(snapshot["wallet"]["balance"] == 9909.91, f"Cash inesperado: {snapshot['wallet']}")
            require(snapshot["total_pnl"] == -0.09, f"PnL inicial inesperado: {snapshot}")
            require(path.is_file(), "O estado paper não foi persistido.")
            shared["isolated_account"] = account
            shared["isolated_orders"] = orders
            shared["isolated_reports"] = list(result.context.execution_reports or [])
            shared["isolated_path"] = path
            return snapshot

    report.run("Pipeline paper persistente", check_core_pipeline)

    def check_mark_to_market() -> dict[str, Any]:
        account: PaperAccount = shared["isolated_account"]
        positions = account.positions.open_positions()
        result = account.mark_to_market({item.id: 0.50 for item in positions})
        snapshot = account.snapshot()
        require(result["positions_updated"] == 2, "Mark não atualizou duas posições.")
        require(snapshot["unrealized_pnl"] == 9.91, f"PnL não realizado inesperado: {snapshot}")
        require(snapshot["equity"] == 10009.91, f"Equity inesperado: {snapshot}")
        return snapshot

    report.run("Mark-to-market e PnL não realizado", check_mark_to_market)

    def check_settlement() -> dict[str, Any]:
        account: PaperAccount = shared["isolated_account"]
        positions = account.positions.open_positions()
        for position in positions:
            account.settle(
                position.id,
                1.0 if position.leg == "YES" else 0.0,
                persist=True,
            )
        snapshot = account.snapshot()
        require(snapshot["open_positions"] == 0, "Ainda existem posições abertas.")
        require(snapshot["closed_positions"] == 2, "As posições não foram encerradas.")
        require(snapshot["realized_pnl"] == 9.91, f"PnL realizado inesperado: {snapshot}")
        require(snapshot["unrealized_pnl"] == 0.0, "PnL não realizado deveria ser zero.")
        require(snapshot["equity"] == 10009.91, f"Equity final inesperado: {snapshot}")
        return snapshot

    report.run("Liquidação e PnL realizado", check_settlement)

    def check_reload() -> dict[str, Any]:
        path: Path = shared["isolated_path"]
        restored = PaperAccount(
            initial_balance=1,
            repository=PaperAccountRepository(path),
            auto_persist=False,
        )
        require(restored.load(), "A conta persistida não foi carregada.")
        snapshot = restored.snapshot()
        require(snapshot["trade_count"] == 4, "Histórico restaurado incompleto.")
        require(snapshot["closed_positions"] == 2, "Posições restauradas incorretas.")
        require(snapshot["equity"] == 10009.91, f"Equity restaurado incorreto: {snapshot}")
        return snapshot

    report.run("Persistência e restauração JSON", check_reload)

    def check_duplicate_guard() -> dict[str, Any]:
        account: PaperAccount = shared["isolated_account"]
        before = account.snapshot()
        try:
            account.commit_execution(
                shared["isolated_orders"],
                shared["isolated_reports"],
                persist=False,
            )
        except ValueError as exc:
            require("já processadas" in str(exc), f"Erro inesperado: {exc}")
        else:
            raise AssertionError("A execução duplicada foi aceita.")
        after = account.snapshot()
        require(before == after, "A rejeição duplicada alterou a conta.")
        return {"blocked": True, "trade_count": after["trade_count"]}

    report.run("Idempotência por order_id", check_duplicate_guard)

    def check_atomic_insufficient_balance() -> dict[str, Any]:
        account = PaperAccount(initial_balance=10, auto_persist=False)
        orders = make_orders("insufficient")
        _, reports = simulate(orders)
        before = account.snapshot()
        try:
            account.commit_execution(orders, reports, persist=False)
        except ValueError as exc:
            require("Saldo paper insuficiente" in str(exc), f"Erro inesperado: {exc}")
        else:
            raise AssertionError("Execução acima do saldo foi aceita.")
        after = account.snapshot()
        require(before == after, "Falha de saldo deixou alterações parciais.")
        return {"atomic": True, "snapshot": after}

    report.run("Saldo e rollback atômico", check_atomic_insufficient_balance)

    before_repositories = repositories()

    def check_http_runtime() -> dict[str, Any]:
        app = create_app()
        with TestClient(app) as client:
            health = client.get("/health").json()
            require(health["lifecycle"].get("paper_account") is True, f"Lifecycle paper inválido: {health}")
            require(health["paper"]["execution_authorized"] is False, "Paper autorizou execução live.")
            reset = client.post("/paper/reset?confirm=RESET-PAPER&persist=true")
            require(reset.status_code == 200, reset.text)

            orders = make_orders("api")
            _, reports = simulate(orders)
            payload = {
                "orders": [item.to_dict() for item in orders],
                "reports": reports,
                "execution_id": "phase5-api-execution",
                "persist": True,
            }
            committed = client.post("/paper/commit", json=payload)
            require(committed.status_code == 200, committed.text)
            account = client.get("/paper/account").json()
            require(account["trade_count"] == 2, f"Conta HTTP inesperada: {account}")
            require(account["open_positions"] == 2, f"Posições HTTP inesperadas: {account}")
            require(account["execution_authorized"] is False, "API paper autorizou live.")
            shared["api_orders"] = orders
            shared["api_reports"] = reports
            shared["api_positions"] = account["positions"]
            return {"health": health["paper"], "account": account}

    report.run("Runtime e API da conta paper", check_http_runtime)

    def check_http_mark_settle_and_restart() -> dict[str, Any]:
        app = create_app()
        with TestClient(app) as client:
            account = client.get("/paper/account").json()
            prices = {item["id"]: 0.50 for item in account["positions"] if item["status"] == "OPEN"}
            marked = client.post("/paper/mark", json={"prices": prices, "persist": True})
            require(marked.status_code == 200, marked.text)
            marked_account = marked.json()["account"]
            require(marked_account["unrealized_pnl"] == 9.91, f"Mark HTTP incorreto: {marked_account}")
            for position in list(marked_account["positions"]):
                if position["status"] != "OPEN":
                    continue
                response = client.post(
                    f"/paper/settle/{position['id']}",
                    json={
                        "settlement_price": 1.0 if position["leg"] == "YES" else 0.0,
                        "persist": True,
                    },
                )
                require(response.status_code == 200, response.text)
            final = client.get("/paper/account").json()
            require(final["realized_pnl"] == 9.91, f"Liquidação HTTP incorreta: {final}")

        paper_account_runtime.account.reset(initial_balance=10_000, persist=False)
        reloaded_app = create_app()
        with TestClient(reloaded_app) as client:
            restored = client.get("/paper/account").json()
            require(restored["trade_count"] == 4, f"Restart não restaurou trades: {restored}")
            require(restored["equity"] == 10009.91, f"Restart não restaurou equity: {restored}")
            return restored

    report.run("API, liquidação e restauração no restart", check_http_mark_settle_and_restart)

    def check_global_isolation() -> dict[str, Any]:
        after = repositories()
        require(after == before_repositories, f"Conta paper alterou OMS live: before={before_repositories}, after={after}")
        return {"before": before_repositories, "after": after, "isolated": True}

    report.run("Isolamento de OMS, Trading e posições live", check_global_isolation)

    def check_live_guard() -> dict[str, Any]:
        calls: list[Any] = []

        def executor(order: Any) -> dict[str, Any]:
            calls.append(order)
            return {"accepted": True}

        result = ExecutionEngine(executor=executor).execute({"id": "phase5-live-guard"})
        require(result["status"] == "DISABLED", f"Live não foi bloqueado: {result}")
        require(calls == [], f"Executor live foi chamado: {calls}")
        return {"result": result, "calls": len(calls)}

    report.run("Execução live permanece bloqueada", check_live_guard)

    payload = report.finish()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    print()
    print("=" * 72)
    print("PREDARB - TESTE REAL / FASE 5 - CONTA PAPER PERSISTENTE")
    print("=" * 72)
    print(f"Aprovados: {payload['summary']['passed']}")
    print(f"Falhas:    {payload['summary']['failed']}")
    print(f"Relatorio: {REPORT_PATH}")
    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
