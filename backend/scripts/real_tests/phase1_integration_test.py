from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Garante que o diretório raiz do backend esteja no sys.path mesmo quando o
# arquivo é executado diretamente por caminho:
# python .\scripts\real_tests\phase1_integration_test.py
# ---------------------------------------------------------------------------
SCRIPT_PATH = Path(__file__).resolve()
BACKEND_ROOT = SCRIPT_PATH.parents[2]

if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Ambiente seguro: estas variáveis são definidas antes de importar o backend.
# Elas têm prioridade sobre o .env apenas durante a execução deste processo.
# ---------------------------------------------------------------------------
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "true",
        "HYPERLIQUID_CONNECTOR_ENABLED": "false",
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
        "DATABASE_URL": "sqlite:///predarb_real_test.db",
    }
)

from fastapi.testclient import TestClient

from app.core.application import create_app
from app.engine.arbitrage_engine import arbitrage_engine
from app.execution.execution_engine import ExecutionEngine


ROOT = BACKEND_ROOT
REPORT_DIR = ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase1_integration_report.json"


class TestReport:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.checks: list[dict[str, Any]] = []

    def run(
        self,
        name: str,
        operation: Callable[[], Any],
    ) -> Any:
        try:
            details = operation()
            self.checks.append(
                {
                    "name": name,
                    "status": "PASS",
                    "details": details,
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

    def finish(self) -> dict[str, Any]:
        finished_at = datetime.now(timezone.utc)
        passed = sum(item["status"] == "PASS" for item in self.checks)
        failed = sum(item["status"] == "FAIL" for item in self.checks)

        return {
            "test": "PredArb Phase 1 - Real Integration",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(),
                3,
            ),
            "environment": {
                "mock_connector": True,
                "hyperliquid_connector": False,
                "initial_market_sync": True,
                "scheduler": False,
                "execution_worker": False,
                "router_dashboard": False,
                "ai_advisory_only": True,
                "ai_execution_authorized": False,
                "database_url": "sqlite:///predarb_real_test.db",
            },
            "summary": {
                "passed": passed,
                "failed": failed,
                "total": len(self.checks),
            },
            "checks": self.checks,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def main() -> int:
    report = TestReport()
    app = create_app()

    try:
        with TestClient(app) as client:
            def check_root() -> dict[str, Any]:
                response = client.get("/")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("status") == "running", f"Resposta inesperada: {data}")
                require(data.get("ai", {}).get("execution_authorized") is False, "AI autorizou execução.")
                return data

            report.run("Aplicação raiz", check_root)

            def check_health() -> dict[str, Any]:
                response = client.get("/health")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("status") == "healthy", f"Health: {data}")
                require(data.get("startup_error") is None, f"Startup error: {data}")
                require(data.get("initial_markets") == 5, f"Mercados iniciais: {data.get('initial_markets')}")
                require(data.get("lifecycle", {}).get("connectors") is True, "Connectors não iniciaram.")
                require(data.get("lifecycle", {}).get("scheduler") is False, "Scheduler deveria estar desligado.")
                require(data.get("lifecycle", {}).get("execution_worker") is False, "Worker deveria estar desligado.")
                require(data.get("ai", {}).get("execution_authorized") is False, "AI autorizou execução.")
                require(data.get("ai", {}).get("auto_load_model") is False, "Auto load de modelo ativo.")
                return data

            report.run("Health e lifecycle", check_health)

            def check_connectors() -> dict[str, Any]:
                response = client.get("/connectors/")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data == ["mock"], f"Connectors inesperados: {data}")
                return {"registered": data}

            report.run("Registro de connectors", check_connectors)

            def check_connector_health() -> dict[str, Any]:
                response = client.get("/connectors/health")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("registered") == 1, f"Registrados: {data}")
                require(data.get("online") == 1, f"Online: {data}")
                require(data.get("errors") == 0, f"Erros: {data}")
                require(data.get("connectors", {}).get("mock", {}).get("connected") is True, f"Mock offline: {data}")
                return data

            report.run("Health do MockConnector", check_connector_health)

            def check_refresh() -> dict[str, Any]:
                response = client.post("/connectors/refresh")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}: {data}")
                require(data.get("status") == "completed", f"Refresh: {data}")
                require(data.get("markets") == 5, f"Mercados: {data}")
                return data

            report.run("Atualização real de mercados mock", check_refresh)

            def check_markets() -> dict[str, Any]:
                response = client.get("/markets/")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(isinstance(data, list), f"Resposta não é lista: {type(data).__name__}")
                require(len(data) == 5, f"Esperados 5 mercados; recebidos {len(data)}")
                require(all(item.get("connector") == "mock" for item in data), "Mercado não-mock encontrado.")
                require(all(item.get("metadata", {}).get("simulated") is True for item in data), "Mercado sem marca de simulação.")
                return {"count": len(data), "platforms": [item.get("platform") for item in data], "sample": data[0]}

            report.run("MarketRepository", check_markets)

            def check_opportunities() -> dict[str, Any]:
                response = client.get("/opportunities/")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(isinstance(data, list), f"Resposta não é lista: {type(data).__name__}")
                require(len(data) > 0, "Nenhuma oportunidade foi encontrada.")
                sample = data[0]
                require(float(sample.get("profit", 0)) > 0, f"Lucro inválido: {sample}")
                require(sample.get("portfolio", {}).get("approved") is True, f"Portfolio não aprovou: {sample}")
                require(sample.get("ai_analysis", {}).get("advisory_only") is True, "AI não está consultiva.")
                require(sample.get("ai_analysis", {}).get("execution_authorized") is False, "AI autorizou execução.")
                return {"count": len(data), "sample": sample}

            report.run("Arbitragem e Pipeline analysis", check_opportunities)

            def check_pipeline_status() -> dict[str, Any]:
                response = client.get("/opportunities/pipeline")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                pipelines = data.get("pipelines", {})
                require(all(name in pipelines for name in ("analysis", "paper", "live")), f"Pipelines ausentes: {pipelines}")
                require("AIStage" in pipelines["analysis"].get("stages", []), "AIStage ausente do analysis.")
                require(pipelines["live"].get("stages", [])[-1] == "ExecutionStage", "ExecutionStage não é o último estágio live.")
                return data

            report.run("Registro dos Pipelines", check_pipeline_status)

            def check_dashboard() -> dict[str, Any]:
                response = client.get("/dashboard/api/snapshot")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("status") in {"ONLINE", "DEGRADED"}, f"Status: {data}")
                require(int(data.get("markets", 0)) == 5, f"Dashboard não refletiu mercados: {data}")
                return {
                    "status": data.get("status"),
                    "markets": data.get("markets"),
                    "opportunities": data.get("opportunities"),
                    "orders": data.get("orders"),
                    "positions": data.get("positions"),
                }

            report.run("Dashboard snapshot", check_dashboard)

            def check_paper() -> dict[str, Any]:
                result = arbitrage_engine.paper_scan()
                require(isinstance(result, dict), f"Resultado inesperado: {type(result).__name__}")
                require(result.get("mode") == "PAPER", f"Modo: {result}")
                require(result.get("status") == "SUCCESS", f"Status: {result}")
                require(result.get("orders_received") == 2, f"Ordens recebidas: {result}")
                require(result.get("orders_filled") == 2, f"Ordens preenchidas: {result}")
                require(result.get("orders_failed") == 0, f"Falhas: {result}")
                require(all(item.get("mode") == "PAPER" for item in result.get("reports", [])), "Relatório não-paper encontrado.")
                return result

            report.run("Paper Trading ponta a ponta", check_paper)

        def check_live_guard() -> dict[str, Any]:
            calls: list[Any] = []

            def real_executor(order: Any) -> dict[str, Any]:
                calls.append(order)
                return {"accepted": True}

            engine = ExecutionEngine(executor=real_executor)
            result = engine.execute({"id": "real-test-live-guard"})
            require(result.get("status") == "DISABLED", f"Live não bloqueado: {result}")
            require(result.get("executed") is False, f"Execução marcada como realizada: {result}")
            require(calls == [], f"Executor foi chamado: {calls}")
            return {"result": result, "executor_calls": len(calls)}

        report.run("Proteção de execução live", check_live_guard)

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
    print("PREDARB — TESTE REAL DE INTEGRAÇÃO / FASE 1")
    print("=" * 72)
    print(f"Aprovados: {payload['summary']['passed']}")
    print(f"Falhas:    {payload['summary']['failed']}")
    print(f"Relatório: {REPORT_PATH}")

    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
