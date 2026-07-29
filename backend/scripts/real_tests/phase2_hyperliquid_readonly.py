from __future__ import annotations

import asyncio
import json
import os
import sys
import traceback
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from math import isfinite
from pathlib import Path
from typing import Any, Awaitable, Callable

# ---------------------------------------------------------------------------
# Resolve a raiz do backend antes de importar app.*.
# scripts/real_tests/arquivo.py -> backend
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# ---------------------------------------------------------------------------
# Ambiente de teste real, porém estritamente somente leitura.
# Estas variáveis prevalecem somente neste processo.
# ---------------------------------------------------------------------------
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "false",
        "HYPERLIQUID_CONNECTOR_ENABLED": "true",
        "INITIAL_MARKET_SYNC_ENABLED": "false",
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
        "DATABASE_URL": "sqlite:///predarb_real_test_phase2.db",
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

from app.clients.hyperliquid import HyperliquidClient
from app.connectors.hyperliquid.connector import HyperliquidConnector
from app.core.application import create_app
from app.core.settings import settings
from app.execution.execution_engine import ExecutionEngine
from app.http.client import HttpClient
from app.parsers.hyperliquid import HyperliquidParser
from app.providers.hyperliquid_provider import HyperliquidProvider


REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase2_hyperliquid_readonly_report.json"


class TestReport:
    def __init__(self) -> None:
        self.started_at = datetime.now(timezone.utc)
        self.checks: list[dict[str, Any]] = []
        self.notes: list[str] = []

    async def run_async(
        self,
        name: str,
        operation: Callable[[], Awaitable[Any]],
    ) -> Any:
        try:
            details = await operation()
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

    def warn(self, message: str) -> None:
        self.notes.append(message)
        print(f"[WARN] {message}")

    def finish(self) -> dict[str, Any]:
        finished_at = datetime.now(timezone.utc)
        passed = sum(item["status"] == "PASS" for item in self.checks)
        failed = sum(item["status"] == "FAIL" for item in self.checks)

        return {
            "test": "PredArb Phase 2 - Hyperliquid Read-Only",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(),
                3,
            ),
            "environment": {
                "mock_connector": False,
                "hyperliquid_connector": True,
                "api_url": settings.HYPERLIQUID_API_URL,
                "initial_market_sync": False,
                "scheduler": False,
                "execution_worker": False,
                "router_dashboard": False,
                "ai_advisory_only": True,
                "ai_execution_authorized": False,
                "database_url": "sqlite:///predarb_real_test_phase2.db",
                "read_only": True,
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


def finite_probability(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    try:
        number = float(value)
    except (TypeError, ValueError):
        return False
    return isfinite(number) and 0 <= number <= 1


def validate_outcome(outcome: Mapping[str, Any]) -> None:
    outcome_id = outcome.get("outcome")
    require(
        isinstance(outcome_id, int) and not isinstance(outcome_id, bool),
        f"Outcome sem id inteiro: {outcome}",
    )

    side_specs = outcome.get("sideSpecs")
    require(
        isinstance(side_specs, Sequence)
        and not isinstance(side_specs, (str, bytes))
        and len(side_specs) >= 2,
        f"Outcome {outcome_id} sem sideSpecs válidos.",
    )

    for side in side_specs[:2]:
        require(isinstance(side, Mapping), f"Lado inválido no outcome {outcome_id}.")
        require(
            isinstance(side.get("name"), str) and side.get("name", "").strip(),
            f"Lado sem nome no outcome {outcome_id}.",
        )


async def run_direct_checks(report: TestReport) -> dict[str, Any]:
    http = HttpClient(
        timeout=settings.HYPERLIQUID_TIMEOUT_SECONDS,
        max_retries=settings.HYPERLIQUID_MAX_RETRIES,
        retry_delay=settings.HYPERLIQUID_RETRY_DELAY_SECONDS,
    )
    client = HyperliquidClient(
        base_url=settings.HYPERLIQUID_API_URL,
        client=http,
    )
    provider = HyperliquidProvider(client=client)
    parser = HyperliquidParser()
    connector = HyperliquidConnector(provider=provider, parser=parser)

    state: dict[str, Any] = {}

    report.run(
        "Guardas de segurança",
        lambda: {
            "api_url": settings.HYPERLIQUID_API_URL,
            "execution_worker": settings.EXECUTION_WORKER_ENABLED,
            "ai_execution_authorized": settings.AI_EXECUTION_AUTHORIZED,
            "auto_load_model": settings.AI_AUTO_LOAD_MODEL,
        }
        if (
            settings.HYPERLIQUID_CONNECTOR_ENABLED
            and not settings.MOCK_CONNECTOR_ENABLED
            and not settings.EXECUTION_WORKER_ENABLED
            and not settings.AI_EXECUTION_AUTHORIZED
            and not settings.AI_AUTO_LOAD_MODEL
        )
        else (_ for _ in ()).throw(
            AssertionError("As guardas de segurança não estão ativas.")
        ),
    )

    async def check_all_mids() -> dict[str, Any]:
        mids = await client.all_mids()
        require(isinstance(mids, Mapping), "allMids não retornou objeto JSON.")
        require(len(mids) > 0, "allMids retornou vazio.")
        state["mids"] = dict(mids)
        outcome_coins = [key for key in mids if str(key).startswith("#")]
        return {
            "assets": len(mids),
            "outcome_side_assets": len(outcome_coins),
            "sample_keys": list(mids.keys())[:10],
        }

    await report.run_async("Hyperliquid allMids", check_all_mids)

    async def check_outcome_meta() -> dict[str, Any]:
        metadata = await client.outcome_meta()
        require(isinstance(metadata, Mapping), "outcomeMeta não retornou objeto JSON.")

        outcomes = metadata.get("outcomes")
        questions = metadata.get("questions", [])

        require(isinstance(outcomes, list), "outcomeMeta.outcomes não é uma lista.")
        require(isinstance(questions, list), "outcomeMeta.questions não é uma lista.")

        for outcome in outcomes[:20]:
            require(isinstance(outcome, Mapping), "Outcome não é um objeto.")
            validate_outcome(outcome)

        state["metadata"] = dict(metadata)
        return {
            "outcomes": len(outcomes),
            "questions": len(questions),
            "sample": dict(outcomes[0]) if outcomes else None,
        }

    await report.run_async("Hyperliquid outcomeMeta", check_outcome_meta)

    def check_encoding() -> dict[str, Any]:
        metadata = state.get("metadata", {})
        mids = state.get("mids", {})
        outcomes = metadata.get("outcomes", []) if isinstance(metadata, Mapping) else []

        if not outcomes:
            report.warn("outcomeMeta não retornou mercados ativos neste momento.")
            return {
                "outcome": None,
                "yes_coin": None,
                "no_coin": None,
                "yes_mid_available": False,
                "no_mid_available": False,
            }

        first = outcomes[0]
        validate_outcome(first)
        outcome_id = int(first["outcome"])
        yes_coin = f"#{10 * outcome_id}"
        no_coin = f"#{10 * outcome_id + 1}"

        return {
            "outcome": outcome_id,
            "yes_coin": yes_coin,
            "no_coin": no_coin,
            "yes_mid_available": yes_coin in mids,
            "no_mid_available": no_coin in mids,
            "yes_mid": mids.get(yes_coin),
            "no_mid": mids.get(no_coin),
        }

    report.run("Codificação HIP-4", check_encoding)

    async def check_provider_snapshot() -> dict[str, Any]:
        snapshot = await provider.get_outcome_snapshot()
        require(isinstance(snapshot, Mapping), "Provider não retornou snapshot.")
        require(isinstance(snapshot.get("metadata"), Mapping), "Metadata inválida.")
        require(isinstance(snapshot.get("mids"), Mapping), "Mids inválidos.")
        require(
            snapshot.get("metadata_error") in (None, ""),
            f"outcomeMeta falhou: {snapshot.get('metadata_error')}",
        )
        state["snapshot"] = dict(snapshot)
        return {
            "outcomes": len(snapshot["metadata"].get("outcomes", [])),
            "assets": len(snapshot["mids"]),
            "metadata_error": snapshot.get("metadata_error"),
        }

    await report.run_async("Provider HIP-4", check_provider_snapshot)

    def check_parser() -> dict[str, Any]:
        snapshot = state.get("snapshot")
        require(isinstance(snapshot, Mapping), "Snapshot ausente para o parser.")

        markets = parser.parse(snapshot)
        require(isinstance(markets, list), "Parser não retornou lista.")

        outcomes = snapshot["metadata"].get("outcomes", [])
        mids = snapshot["mids"]
        parseable = 0

        for outcome in outcomes:
            if not isinstance(outcome, Mapping):
                continue
            outcome_id = outcome.get("outcome")
            if not isinstance(outcome_id, int) or isinstance(outcome_id, bool):
                continue
            yes = mids.get(f"#{10 * outcome_id}")
            no = mids.get(f"#{10 * outcome_id + 1}")
            if finite_probability(yes) and finite_probability(no):
                parseable += 1

        if parseable > 0:
            require(
                len(markets) > 0,
                "Existem outcomes com dois mids válidos, mas o parser retornou zero mercados.",
            )
        elif outcomes:
            report.warn(
                "Há outcomes ativos, mas nenhum possuía simultaneamente mids válidos para os dois lados."
            )

        for market in markets[:10]:
            require(market.get("connector") == "hyperliquid", "Connector inválido.")
            require(finite_probability(market.get("yes")), "Preço YES inválido.")
            require(finite_probability(market.get("no")), "Preço NO inválido.")
            require(market.get("market_id"), "market_id ausente.")

        state["markets"] = markets
        return {
            "outcomes": len(outcomes),
            "parseable_candidates": parseable,
            "markets_parsed": len(markets),
            "sample": markets[0] if markets else None,
        }

    report.run("Parser Hyperliquid", check_parser)

    async def check_connector() -> dict[str, Any]:
        connected = await connector.connect()
        require(connected is True, "HyperliquidConnector não conectou.")

        health = await connector.health()
        health_dict = health.to_dict()
        require(health_dict.get("connected") is True, f"Health offline: {health_dict}")
        require(not health_dict.get("error"), f"Health com erro: {health_dict}")

        markets = await connector.get_markets()
        require(isinstance(markets, list), "get_markets não retornou lista.")

        status = connector.get_status().to_dict()
        require(status.get("connected") is True, f"Status desconectado: {status}")
        require(status.get("markets") == len(markets), "Contagem de mercados divergente.")

        await connector.disconnect()

        return {
            "connected": connected,
            "health": health_dict,
            "markets": len(markets),
            "status_before_disconnect": status,
        }

    await report.run_async("Ciclo real do HyperliquidConnector", check_connector)

    await client.close()
    return state


def run_application_check(report: TestReport) -> dict[str, Any] | None:
    app = create_app()

    def operation() -> dict[str, Any]:
        with TestClient(app) as client:
            root_response = client.get("/")
            require(root_response.status_code == 200, f"Root HTTP {root_response.status_code}")
            root = root_response.json()
            require(root.get("ai", {}).get("execution_authorized") is False, "AI autorizou execução.")

            health_response = client.get("/health")
            require(health_response.status_code == 200, f"Health HTTP {health_response.status_code}")
            health = health_response.json()
            require(health.get("status") == "healthy", f"Health inválido: {health}")
            require(health.get("startup_error") is None, f"Startup error: {health}")
            require(health.get("lifecycle", {}).get("connectors") is True, "Connectors não iniciaram.")
            require(health.get("lifecycle", {}).get("scheduler") is False, "Scheduler foi ligado.")
            require(health.get("lifecycle", {}).get("execution_worker") is False, "Worker foi ligado.")
            require(health.get("ai", {}).get("execution_authorized") is False, "AI autorizou execução.")

            connectors_response = client.get("/connectors/")
            require(connectors_response.status_code == 200, "Falha ao listar connectors.")
            connectors = connectors_response.json()
            require(connectors == ["hyperliquid"], f"Connectors inesperados: {connectors}")

            connector_health_response = client.get("/connectors/health")
            require(connector_health_response.status_code == 200, "Health dos connectors falhou.")
            connector_health = connector_health_response.json()
            require(connector_health.get("registered") == 1, f"Registro inválido: {connector_health}")
            require(connector_health.get("online") == 1, f"Hyperliquid offline: {connector_health}")
            require(connector_health.get("errors") == 0, f"Erro no conector: {connector_health}")

            refresh_response = client.post("/connectors/refresh")
            require(refresh_response.status_code == 200, f"Refresh HTTP {refresh_response.status_code}: {refresh_response.text}")
            refresh = refresh_response.json()
            require(refresh.get("status") == "completed", f"Refresh inválido: {refresh}")

            markets_response = client.get("/markets/")
            require(markets_response.status_code == 200, "Endpoint /markets falhou.")
            markets = markets_response.json()
            require(isinstance(markets, list), "/markets não retornou lista.")
            require(refresh.get("markets") == len(markets), "Refresh e repository divergem.")

            status_response = client.get("/connectors/hyperliquid")
            require(status_response.status_code == 200, "Status do conector falhou.")
            status = status_response.json()
            require(status.get("connected") is True, f"Status offline: {status}")
            require(not status.get("error"), f"Status com erro: {status}")

            return {
                "root": root,
                "health": {
                    "status": health.get("status"),
                    "lifecycle": health.get("lifecycle"),
                    "ai": health.get("ai"),
                },
                "connectors": connectors,
                "connector_health": connector_health,
                "refresh": refresh,
                "repository_markets": len(markets),
                "connector_status": status,
            }

    return report.run("Aplicação HTTP com Hyperliquid", operation)


def run_live_guard(report: TestReport) -> dict[str, Any] | None:
    def operation() -> dict[str, Any]:
        calls: list[Any] = []

        def executor(order: Any) -> dict[str, Any]:
            calls.append(order)
            return {"accepted": True}

        engine = ExecutionEngine(executor=executor)
        result = engine.execute({"id": "phase2-readonly-live-guard"})

        require(result.get("status") == "DISABLED", f"Live não bloqueado: {result}")
        require(result.get("executed") is False, f"Execução marcada como realizada: {result}")
        require(calls == [], f"Executor foi chamado: {calls}")

        return {
            "result": result,
            "executor_calls": len(calls),
        }

    return report.run("Proteção de execução live", operation)


async def async_main(report: TestReport) -> None:
    await run_direct_checks(report)


def main() -> int:
    print("=" * 72)
    print("PREDARB — TESTE REAL HYPERLIQUID / FASE 2 / SOMENTE LEITURA")
    print("=" * 72)
    print(f"API: {settings.HYPERLIQUID_API_URL}")
    print("Execução live: BLOQUEADA")
    print()

    report = TestReport()

    try:
        asyncio.run(async_main(report))
        run_application_check(report)
        run_live_guard(report)
    except KeyboardInterrupt:
        report.warn("Teste interrompido pelo usuário.")
    finally:
        payload = report.finish()
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2, default=str),
            encoding="utf-8",
        )

    summary = payload["summary"]
    print()
    print("=" * 72)
    print(f"Aprovados: {summary['passed']}")
    print(f"Falhas:    {summary['failed']}")
    print(f"Avisos:    {summary['warnings']}")
    print(f"Relatório: {REPORT_PATH}")
    print("=" * 72)

    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
