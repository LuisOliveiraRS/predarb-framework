from __future__ import annotations

import json
import os
import sys
import traceback
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Ambiente seguro e determinístico desta fase.
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "true",
        "HYPERLIQUID_CONNECTOR_ENABLED": "true",
        "INITIAL_MARKET_SYNC_ENABLED": "true",
        "SCHEDULER_ENABLED": "false",
        "EXECUTION_WORKER_ENABLED": "false",
        "ROUTER_DASHBOARD_ENABLED": "false",
        "AI_ENABLED": "true",
        "AI_PIPELINE_ENABLED": "true",
        "AI_STRICT_FEATURES": "false",
        "AI_FAIL_ON_ERROR": "false",
        "AI_ADVISORY_ONLY": "true",
        "AI_EXECUTION_AUTHORIZED": "false",
        "AI_AUTO_LOAD_MODEL": "false",
        "DATABASE_URL": "sqlite:///predarb_real_test_phase4.db",
        "HYPERLIQUID_API_URL": os.environ.get(
            "HYPERLIQUID_API_URL",
            "https://api.hyperliquid.xyz",
        ),
        "HYPERLIQUID_TIMEOUT_SECONDS": os.environ.get(
            "HYPERLIQUID_TIMEOUT_SECONDS",
            "15",
        ),
        "HYPERLIQUID_MAX_RETRIES": os.environ.get(
            "HYPERLIQUID_MAX_RETRIES",
            "1",
        ),
        "HYPERLIQUID_RETRY_DELAY_SECONDS": os.environ.get(
            "HYPERLIQUID_RETRY_DELAY_SECONDS",
            "0.5",
        ),
    }
)

from fastapi.testclient import TestClient

from app.core.application import create_app
from app.execution.execution_engine import ExecutionEngine
from app.market.comparators.cross_platform import CrossPlatformComparator
from app.orders.fill_repository import fill_repository
from app.orders.order_repository import order_repository
from app.paper.paper_trade_history import paper_trade_history
from app.paper.paper_wallet import paper_wallet
from app.pipeline.pipeline_builder import PipelineBuilder
from app.pipeline.pipeline_manager import pipeline_manager
from app.positions.position_repository import position_repository
from app.trading.trade_repository import trade_repository


REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase4_paper_trading_report.json"


class TestReport:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.checks: list[dict[str, Any]] = []
        self.notes: list[str] = []

    def run(self, name: str, operation: Callable[[], Any]) -> Any:
        try:
            details = operation()
            self.checks.append(
                {
                    "name": name,
                    "status": "PASS",
                    "details": plain(details),
                }
            )
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

    def warn(self, message: str) -> None:
        self.notes.append(message)
        print(f"[WARN] {message}")

    def finish(self) -> dict[str, Any]:
        finished_at = datetime.now(timezone.utc)
        passed = sum(item["status"] == "PASS" for item in self.checks)
        failed = sum(item["status"] == "FAIL" for item in self.checks)
        return {
            "test": "PredArb Phase 4 - Controlled Paper Trading",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(),
                3,
            ),
            "environment": {
                "mock_connector": True,
                "hyperliquid_connector": True,
                "scheduler": False,
                "execution_worker": False,
                "ai_advisory_only": True,
                "ai_execution_authorized": False,
                "external_connector_read_only": True,
                "paper_control_market": True,
            },
            "summary": {
                "passed": passed,
                "failed": failed,
                "total": len(self.checks),
                "warnings": len(self.notes),
            },
            "notes": self.notes,
            "checks": self.checks,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_field(target: Any, name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(name, default)
    return getattr(target, name, default)


def plain(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, Mapping):
        return {str(key): plain(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [plain(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        return plain(to_dict())
    slots = getattr(value.__class__, "__slots__", ())
    if slots:
        return {
            str(name): plain(getattr(value, name))
            for name in slots
            if hasattr(value, name)
        }
    if hasattr(value, "__dict__"):
        return plain(vars(value))
    return str(value)


def repository_snapshot() -> dict[str, Any]:
    positions = position_repository.all()
    return {
        "orders": order_repository.count(),
        "fills": fill_repository.count(),
        "trades": trade_repository.count(),
        "positions": len(list(positions or [])),
        "paper_history": len(list(paper_trade_history.all() or [])),
        "paper_wallet_balance": float(paper_wallet.balance),
        "paper_wallet_locked": float(paper_wallet.locked),
    }


def choose_hyperliquid_market(markets: list[Any]) -> Any:
    candidates: list[Any] = []
    for market in markets:
        connector = str(read_field(market, "connector", "")).strip().casefold()
        if connector != "hyperliquid":
            continue
        question = str(read_field(market, "question", "")).strip()
        try:
            yes = float(read_field(market, "yes", -1))
            no = float(read_field(market, "no", -1))
        except (TypeError, ValueError):
            continue
        if question and 0 < yes < 1 and 0 < no < 1:
            candidates.append(market)

    if not candidates:
        raise AssertionError(
            "Nenhum mercado Hyperliquid com preços binários válidos foi encontrado."
        )

    # Prefere um mercado com o menor lado mais afastado dos extremos.
    candidates.sort(
        key=lambda market: abs(
            min(
                float(read_field(market, "yes", 0)),
                float(read_field(market, "no", 0)),
            )
            - 0.5
        )
    )
    return candidates[0]


def build_control_market(live_market: Any) -> dict[str, Any]:
    yes = float(read_field(live_market, "yes"))
    no = float(read_field(live_market, "no"))
    target_cost = 0.90

    if yes <= no:
        control_no = target_cost - yes
        require(0 < control_no < 1, "Não foi possível formar a perna No controlada.")
        control_yes = 1.0 - control_no
        expected_route = "HYPERLIQUID_YES_CONTROL_NO"
    else:
        control_yes = target_cost - no
        require(0 < control_yes < 1, "Não foi possível formar a perna Yes controlada.")
        control_no = 1.0 - control_yes
        expected_route = "CONTROL_YES_HYPERLIQUID_NO"

    liquidity = max(
        10_000.0,
        float(read_field(live_market, "liquidity", 0) or 0),
        float(read_field(live_market, "volume", 0) or 0),
    )
    source_market_id = str(read_field(live_market, "market_id", "unknown")).strip()

    return {
        "platform": "Phase4PaperControl",
        "question": str(read_field(live_market, "question", "")).strip(),
        "yes": round(control_yes, 6),
        "no": round(control_no, 6),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "connector": "phase4_control",
        "liquidity": liquidity,
        "volume": liquidity,
        "fee": 0.0,
        "market_id": f"phase4-control:{source_market_id}",
        "category": str(read_field(live_market, "category", "")),
        "asset": str(read_field(live_market, "asset", "")),
        "event_type": str(read_field(live_market, "event_type", "")),
        "expires_at": plain(read_field(live_market, "expires_at", None)),
        "status": "open",
        "metadata": {
            "simulated": True,
            "paper_only": True,
            "source_connector": "hyperliquid",
            "source_market_id": source_market_id,
            "expected_route": expected_route,
            "target_cost": target_cost,
        },
    }


def order_ids(result: Any) -> set[str]:
    return {
        str(read_field(order, "id", ""))
        for order in list(result.context.orders or [])
        if str(read_field(order, "id", ""))
    }


def main() -> int:
    report = TestReport()
    app = create_app()
    shared: dict[str, Any] = {}

    try:
        with TestClient(app) as client:
            def check_safety_and_health() -> dict[str, Any]:
                response = client.get("/health")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("status") == "healthy", f"Health inesperado: {data}")
                configuration = data.get("connector_configuration", {})
                require(configuration.get("mock_enabled") is True, "MockConnector está desligado.")
                require(
                    configuration.get("hyperliquid_enabled") is True,
                    "HyperliquidConnector está desligado.",
                )
                require(data.get("lifecycle", {}).get("scheduler") is False, "Scheduler deveria estar desligado.")
                require(
                    data.get("lifecycle", {}).get("execution_worker") is False,
                    "Execution Worker deveria estar desligado.",
                )
                ai = data.get("ai", {})
                require(ai.get("advisory_only") is True, "AI não está consultiva.")
                require(ai.get("execution_authorized") is False, "AI autorizou execução.")
                require(ai.get("auto_load_model") is False, "Auto load de modelo ativo.")
                return {
                    "status": data.get("status"),
                    "connector_configuration": configuration,
                    "scheduler": data.get("scheduler"),
                    "ai": ai,
                }

            report.run("Guardas e lifecycle", check_safety_and_health)

            def check_real_market_feed() -> dict[str, Any]:
                refresh = client.post("/connectors/refresh")
                refresh_data = refresh.json()
                require(refresh.status_code == 200, f"Refresh HTTP {refresh.status_code}: {refresh_data}")
                require(refresh_data.get("status") == "completed", f"Refresh falhou: {refresh_data}")

                markets_response = client.get("/markets/")
                markets = markets_response.json()
                require(markets_response.status_code == 200, f"Markets HTTP {markets_response.status_code}")
                require(isinstance(markets, list), "A resposta de mercados não é uma lista.")
                require(any(str(item.get("connector", "")).casefold() == "mock" for item in markets), "Mercados mock ausentes.")
                require(
                    any(str(item.get("connector", "")).casefold() == "hyperliquid" for item in markets),
                    "Mercados Hyperliquid ausentes.",
                )
                live_market = choose_hyperliquid_market(markets)
                shared["markets"] = markets
                shared["live_market"] = live_market
                return {
                    "total_markets": len(markets),
                    "mock_markets": sum(str(item.get("connector", "")).casefold() == "mock" for item in markets),
                    "hyperliquid_markets": sum(
                        str(item.get("connector", "")).casefold() == "hyperliquid"
                        for item in markets
                    ),
                    "selected_market": live_market,
                    "refresh": refresh_data,
                }

            report.run("Feed real somente leitura", check_real_market_feed)

            def check_controlled_cross_platform_route() -> dict[str, Any]:
                live_market = shared["live_market"]
                control_market = build_control_market(live_market)
                comparator = CrossPlatformComparator()
                opportunities = comparator.compare([live_market, control_market])
                require(opportunities, "O comparator não formou a oportunidade controlada.")

                profitable = [
                    item
                    for item in opportunities
                    if float(item.get("cost", 1.0)) < 1.0
                    and {
                        str(item.get("buy_yes_platform", "")).casefold(),
                        str(item.get("buy_no_platform", "")).casefold(),
                    }
                    == {"hyperliquid", "phase4papercontrol"}
                ]
                require(profitable, f"Nenhuma rota controlada lucrativa: {opportunities}")
                shared["raw_opportunities"] = profitable
                shared["control_market"] = control_market
                return {
                    "control_market": control_market,
                    "opportunities": profitable,
                }

            report.run("Rota cross-platform controlada", check_controlled_cross_platform_route)

            def check_analysis_pipeline() -> dict[str, Any]:
                result = pipeline_manager.execute(
                    deepcopy(shared["raw_opportunities"]),
                    pipeline_name=pipeline_manager.ANALYSIS_PIPELINE,
                )
                require(result.success, f"Pipeline analysis retornou erros: {result.errors}")
                require(not result.halted, f"Pipeline analysis foi interrompido: {result.context.halt_reason}")
                require(result.opportunities, "Pipeline analysis não aprovou a oportunidade.")

                opportunity = result.opportunities[0]
                require(read_field(opportunity, "approved", False) is True, "FilterStage não aprovou a oportunidade.")
                portfolio = read_field(opportunity, "portfolio", {})
                require(read_field(portfolio, "approved", False) is True, "PortfolioStage não aprovou a oportunidade.")
                analysis = read_field(opportunity, "ai_analysis", {})
                require(read_field(analysis, "advisory_only", False) is True, "AI não está consultiva.")
                require(
                    read_field(analysis, "execution_authorized", True) is False,
                    "AI autorizou execução.",
                )
                shared["approved_opportunities"] = result.opportunities
                return result.to_dict()

            report.run("Pipeline analysis e AI consultiva", check_analysis_pipeline)

            before = repository_snapshot()
            shared["before"] = before

            def check_official_paper_pipeline() -> dict[str, Any]:
                result = pipeline_manager.execute(
                    deepcopy(shared["raw_opportunities"]),
                    pipeline_name=pipeline_manager.PAPER_PIPELINE,
                )
                require(result.success, f"Pipeline paper retornou erros: {result.errors}")
                summary = result.output
                require(isinstance(summary, Mapping), f"Resumo paper inesperado: {type(summary).__name__}")
                require(summary.get("mode") == "PAPER", f"Modo incorreto: {summary}")
                require(summary.get("status") == "SUCCESS", f"Paper não concluiu: {summary}")
                require(summary.get("orders_received") == 2, f"Ordens recebidas inválidas: {summary}")
                require(summary.get("orders_filled") == 2, f"Ordens preenchidas inválidas: {summary}")
                require(summary.get("orders_failed") == 0, f"Falhas de paper: {summary}")

                orders = list(result.context.orders or [])
                reports = list(result.context.execution_reports or [])
                require(len(orders) == 2, f"O OrderStage gerou {len(orders)} ordens.")
                require(len(reports) == 2, f"O PaperStage gerou {len(reports)} fills simulados.")
                require({str(read_field(order, "leg", "")).upper() for order in orders} == {"YES", "NO"}, "As pernas YES/NO não foram geradas.")
                require(len(order_ids(result)) == 2, "IDs de ordem não são únicos.")
                require(all(report_item.get("status") == "FILLED" for report_item in reports), "Um relatório não foi preenchido.")
                require(all(report_item.get("mode") == "PAPER" for report_item in reports), "Um relatório não está em modo PAPER.")
                require(all(float(report_item.get("filled_quantity", 0)) > 0 for report_item in reports), "Quantidade preenchida inválida.")
                require(all(0 < float(report_item.get("average_price", 0)) <= 1 for report_item in reports), "Preço médio inválido.")
                require(
                    result.context.metadata.get("paper_execution", {}).get("status") == "SUCCESS",
                    "Metadata de execução paper inválida.",
                )
                shared["first_paper_ids"] = order_ids(result)
                shared["first_paper_summary"] = summary
                return result.to_dict()

            report.run("Paper Trading oficial ponta a ponta", check_official_paper_pipeline)

            def check_fee_and_replay() -> dict[str, Any]:
                pipeline = PipelineBuilder().build_paper(paper_fee_rate=0.001)
                cycles: list[dict[str, Any]] = []
                all_ids: set[str] = set()

                for cycle in range(1, 4):
                    result = pipeline.execute(deepcopy(shared["raw_opportunities"]))
                    require(result.success, f"Replay {cycle} falhou: {result.errors}")
                    summary = result.output
                    ids = order_ids(result)
                    require(len(ids) == 2, f"Replay {cycle} não gerou duas ordens.")
                    require(not all_ids.intersection(ids), f"Replay {cycle} reutilizou IDs de ordens.")
                    all_ids.update(ids)
                    require(summary.get("status") == "SUCCESS", f"Replay {cycle}: {summary}")
                    require(float(summary.get("total_fees", 0)) > 0, "Fee paper não foi aplicada.")
                    cycles.append(
                        {
                            "cycle": cycle,
                            "order_ids": sorted(ids),
                            "summary": summary,
                        }
                    )

                return {
                    "cycles": cycles,
                    "unique_order_ids": len(all_ids),
                    "fee_rate": 0.001,
                }

            report.run("Replay e fees do Paper Trading", check_fee_and_replay)

            def check_isolation() -> dict[str, Any]:
                after = repository_snapshot()
                before_snapshot = shared["before"]
                require(after == before_snapshot, f"Paper Trading alterou estado global: before={before_snapshot}, after={after}")
                return {
                    "before": before_snapshot,
                    "after": after,
                    "isolated": True,
                }

            report.run("Isolamento de OMS, Trading e Portfolio", check_isolation)

            def check_live_pipeline_guard() -> dict[str, Any]:
                result = pipeline_manager.execute(
                    deepcopy(shared["raw_opportunities"]),
                    pipeline_name=pipeline_manager.LIVE_PIPELINE,
                )
                metadata = result.context.metadata.get("live_execution", {})
                require(metadata.get("enabled") is False, f"Live foi habilitado: {metadata}")
                require(metadata.get("status") == "DISABLED", f"Live não está bloqueado: {metadata}")
                require(len(list(result.context.orders or [])) == 2, "O plano live não gerou as duas intenções esperadas.")
                return {
                    "metadata": metadata,
                    "orders_available": len(list(result.context.orders or [])),
                }

            report.run("Pipeline live permanece bloqueado", check_live_pipeline_guard)

        def check_executor_guard() -> dict[str, Any]:
            calls: list[Any] = []

            def executor(order: Any) -> dict[str, Any]:
                calls.append(order)
                return {"accepted": True}

            engine = ExecutionEngine(executor=executor)
            result = engine.execute({"id": "phase4-live-guard"})
            require(result.get("status") == "DISABLED", f"ExecutionEngine não bloqueou: {result}")
            require(result.get("executed") is False, f"Execução marcada como realizada: {result}")
            require(calls == [], f"Executor real foi chamado: {calls}")
            return {"result": result, "executor_calls": len(calls)}

        report.run("Executor real não chamado", check_executor_guard)

    except Exception as exc:
        report.checks.append(
            {
                "name": "Ciclo de vida da aplicação",
                "status": "FAIL",
                "error": str(exc),
                "traceback": traceback.format_exc(),
            }
        )
        print(f"[FAIL] Ciclo de vida da aplicação: {exc}")

    payload = report.finish()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("PREDARB — TESTE REAL / FASE 4 — PAPER TRADING")
    print("=" * 72)
    print(f"Aprovados: {payload['summary']['passed']}")
    print(f"Falhas:    {payload['summary']['failed']}")
    print(f"Avisos:    {payload['summary']['warnings']}")
    print(f"Relatório: {REPORT_PATH}")

    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
