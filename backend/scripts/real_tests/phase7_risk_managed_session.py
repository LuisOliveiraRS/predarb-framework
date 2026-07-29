from __future__ import annotations

import asyncio
import json
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any, Callable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.execution.execution_engine import ExecutionEngine
from app.market.comparators.cross_platform import CrossPlatformComparator
from app.paper.paper_account import PaperAccount
from app.paper.paper_equity_tracker import PaperEquityTracker
from app.paper.paper_position_manager import PaperPositionManager
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_risk import PaperRiskGuard, PaperRiskLimits
from app.paper.paper_session import PaperSessionManager, PaperSessionRepository
from app.paper.paper_session_runtime import PaperSessionRuntime
from app.paper.paper_trade_history import PaperTradeHistory
from app.paper.paper_wallet import PaperWallet

REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase7_risk_managed_session_report.json"


class Report:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.checks: list[dict[str, Any]] = []

    def run(self, name: str, operation: Callable[[], Any]) -> Any:
        try:
            details = operation()
            self.checks.append({"name": name, "status": "PASS", "details": details})
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
            "test": "PredArb Phase 7 - Risk Managed Paper Session",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(), 3
            ),
            "summary": {"passed": passed, "failed": failed, "total": len(self.checks)},
            "checks": self.checks,
            "execution_authorized": False,
            "live_execution": False,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def build_opportunities() -> list[dict[str, Any]]:
    markets = [
        {
            "platform": "Phase7-A",
            "question": "Will the Phase 7 paper session pass?",
            "yes": 0.40,
            "no": 0.60,
            "liquidity": 10_000,
            "volume": 10_000,
            "market_id": "phase7-a",
        },
        {
            "platform": "Phase7-B",
            "question": "Will the Phase 7 paper session pass?",
            "yes": 0.55,
            "no": 0.45,
            "liquidity": 10_000,
            "volume": 10_000,
            "market_id": "phase7-b",
        },
    ]
    opportunities = CrossPlatformComparator().compare(markets)
    require(bool(opportunities), "O comparator não criou a oportunidade controlada.")
    return opportunities


def build_account(path: Path) -> PaperAccount:
    return PaperAccount(
        initial_balance=10_000,
        wallet=PaperWallet(10_000),
        history=PaperTradeHistory(),
        positions=PaperPositionManager(),
        equity_tracker=PaperEquityTracker(max_points=200),
        repository=PaperAccountRepository(path),
        auto_persist=False,
    )


def limits(**overrides: Any) -> PaperRiskLimits:
    values: dict[str, Any] = {
        "max_trade_notional": 500,
        "max_total_exposure": 2_500,
        "max_market_exposure": 300,
        "max_open_positions": 10,
        "max_daily_trades": 20,
        "daily_loss_limit": 500,
        "max_drawdown_rate": 0.20,
        "min_roi": 0,
        "min_confidence": 0,
        "max_risk_score": 100,
    }
    values.update(overrides)
    return PaperRiskLimits(**values)


def main() -> int:
    report = Report()

    with TemporaryDirectory() as directory:
        root = Path(directory)
        opportunities = build_opportunities()
        account = build_account(root / "account.json")
        guard = PaperRiskGuard(account=account, limits=limits())
        manager = PaperSessionManager(
            account=account,
            risk_guard=guard,
            opportunity_source=lambda: opportunities,
            repository=PaperSessionRepository(root / "session.json"),
            stake_amount=250,
            max_opportunities_per_cycle=1,
            paper_fee_rate=0.001,
        )

        report.run(
            "Guardas operacionais",
            lambda: {
                "risk": guard.status(),
                "execution_authorized": False,
                "live_execution": False,
            },
        )

        def first_cycle() -> dict[str, Any]:
            cycle = manager.run_cycle()
            require(cycle["status"] == "SUCCESS", f"Ciclo inesperado: {cycle}")
            require(cycle["orders"] == 2, "O ciclo deveria gerar duas ordens Paper.")
            require(cycle["fills"] == 2, "O ciclo deveria gerar dois fills Paper.")
            snapshot = account.snapshot(include_trades=False)
            require(snapshot["trade_count"] == 2, "A conta não registrou os dois trades.")
            require(snapshot["execution_authorized"] is False, "Execução live foi autorizada.")
            return cycle

        report.run("Primeiro ciclo Paper aprovado", first_cycle)

        def market_exposure_stop() -> dict[str, Any]:
            cycle = manager.run_cycle()
            require(
                cycle["status"] == "RISK_REJECTED",
                f"A exposição por mercado deveria rejeitar o segundo ciclo: {cycle}",
            )
            codes = {
                code
                for item in cycle.get("risk", {}).get("rejections", [])
                for code in item.get("codes", [])
            }
            require(
                "MARKET_EXPOSURE_LIMIT" in codes,
                f"Código de exposição ausente: {codes}",
            )
            return {"status": cycle["status"], "codes": sorted(codes)}

        report.run("Limite de exposição por mercado", market_exposure_stop)

        def report_persistence() -> dict[str, Any]:
            require((root / "session.json").is_file(), "Relatório JSON não foi criado.")
            restored_account = build_account(root / "restored-account.json")
            restored_manager = PaperSessionManager(
                account=restored_account,
                risk_guard=PaperRiskGuard(account=restored_account, limits=limits()),
                opportunity_source=lambda: [],
                repository=PaperSessionRepository(root / "session.json"),
                stake_amount=250,
            )
            require(restored_manager.restore_report() is True, "Relatório não foi restaurado.")
            restored = restored_manager.report()
            require(restored["total_cycles"] == 2, f"Total restaurado inválido: {restored}")
            return {
                "path": str(root / "session.json"),
                "cycles": restored["total_cycles"],
            }

        report.run("Persistência do relatório da sessão", report_persistence)

        def daily_stop() -> dict[str, Any]:
            stopped_account = build_account(root / "daily-account.json")
            stopped_guard = PaperRiskGuard(
                account=stopped_account,
                limits=limits(max_market_exposure=1_000, daily_loss_limit=0.10),
            )
            stopped_manager = PaperSessionManager(
                account=stopped_account,
                risk_guard=stopped_guard,
                opportunity_source=lambda: opportunities,
                repository=PaperSessionRepository(root / "daily-session.json"),
                stake_amount=250,
                paper_fee_rate=0.001,
            )
            first = stopped_manager.run_cycle()
            require(first["status"] == "SUCCESS", "O primeiro ciclo diário falhou.")
            second = stopped_manager.run_cycle()
            require(second["status"] == "RISK_STOPPED", f"Stop diário não atuou: {second}")
            require(
                "DAILY_LOSS_LIMIT" in second["risk"]["codes"],
                "Código DAILY_LOSS_LIMIT ausente.",
            )
            return second["risk"]

        report.run("Stop diário por perda", daily_stop)

        def runtime_confirmation() -> dict[str, Any]:
            runtime_account = build_account(root / "runtime-account.json")
            runtime_manager = PaperSessionManager(
                account=runtime_account,
                risk_guard=PaperRiskGuard(account=runtime_account, limits=limits()),
                opportunity_source=lambda: [],
                repository=PaperSessionRepository(root / "runtime-session.json"),
                stake_amount=250,
            )
            runtime = PaperSessionRuntime(
                manager=runtime_manager,
                enabled=True,
                interval_seconds=1,
            )

            async def scenario() -> dict[str, Any]:
                invalid_blocked = False
                try:
                    await runtime.start(confirm="INVALID")
                except ValueError:
                    invalid_blocked = True
                require(invalid_blocked, "O runtime aceitou confirmação inválida.")
                started = await runtime.start(confirm=runtime.START_CONFIRMATION)
                require(started["running"] is True, "Runtime não iniciou.")
                await asyncio.sleep(0.05)
                stopped = await runtime.stop()
                require(stopped["running"] is False, "Runtime não encerrou.")
                return stopped

            return asyncio.run(scenario())

        report.run("Runtime com confirmação explícita", runtime_confirmation)

        def live_guard() -> dict[str, Any]:
            calls: list[Any] = []

            def executor(order: Any) -> dict[str, Any]:
                calls.append(order)
                return {"accepted": True}

            result = ExecutionEngine(executor=executor).execute({"id": "phase7-live"})
            require(result["status"] == "DISABLED", f"Live não foi bloqueado: {result}")
            require(calls == [], "O executor live foi chamado.")
            return result

        report.run("Execução live bloqueada", live_guard)

    result = report.finish()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print()
    print(f"Aprovados: {result['summary']['passed']}")
    print(f"Falhas:    {result['summary']['failed']}")
    print(f"Relatório: {REPORT_PATH}")
    return 0 if result["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
