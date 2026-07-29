from __future__ import annotations

import json
import os
import sys
import threading
import time
import traceback
from collections.abc import Mapping
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

# ---------------------------------------------------------------------------
# Resolve a raiz do backend antes de importar app.*.
# scripts/real_tests/arquivo.py -> backend
# ---------------------------------------------------------------------------
BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

INTERVAL_SECONDS = max(
    3,
    int(os.environ.get("PREDARB_PHASE3_INTERVAL_SECONDS", "5")),
)
OBSERVATION_SECONDS = max(
    INTERVAL_SECONDS * 2 + 3,
    int(os.environ.get("PREDARB_PHASE3_OBSERVATION_SECONDS", "18")),
)

# ---------------------------------------------------------------------------
# Ambiente da Fase 3: duas fontes, scheduler controlado e nenhuma execução.
# Estas variáveis valem apenas para este processo.
# ---------------------------------------------------------------------------
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "true",
        "HYPERLIQUID_CONNECTOR_ENABLED": "true",
        "INITIAL_MARKET_SYNC_ENABLED": "true",
        "SCHEDULER_ENABLED": "true",
        "MARKET_UPDATE_INTERVAL_SECONDS": str(INTERVAL_SECONDS),
        "EXECUTION_WORKER_ENABLED": "false",
        "ROUTER_DASHBOARD_ENABLED": "false",
        "AI_ENABLED": "true",
        "AI_PIPELINE_ENABLED": "true",
        "AI_STRICT_FEATURES": "false",
        "AI_FAIL_ON_ERROR": "false",
        "AI_ADVISORY_ONLY": "true",
        "AI_EXECUTION_AUTHORIZED": "false",
        "AI_AUTO_LOAD_MODEL": "false",
        "DATABASE_URL": "sqlite:///predarb_real_test_phase3.db",
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
from app.core.settings import settings
from app.events.event_bus import event_bus
from app.execution.execution_engine import ExecutionEngine
from app.repositories.market_repository import market_repository
from app.scheduler.scheduler import scheduler_service
from app.scheduler.tasks import MARKET_UPDATED_EVENT


REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase3_scheduler_stability_report.json"


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
            "test": "PredArb Phase 3 - Dual Connector Scheduler Stability",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "duration_seconds": round(
                (finished_at - self.started_at).total_seconds(),
                3,
            ),
            "environment": {
                "mock_connector": True,
                "hyperliquid_connector": True,
                "initial_market_sync": True,
                "scheduler": True,
                "market_update_interval_seconds": INTERVAL_SECONDS,
                "observation_seconds": OBSERVATION_SECONDS,
                "execution_worker": False,
                "router_dashboard": False,
                "ai_advisory_only": True,
                "ai_execution_authorized": False,
                "database_url": "sqlite:///predarb_real_test_phase3.db",
                "read_only_external_connector": True,
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


def market_identity(market: Any) -> tuple[str, str, str]:
    connector = str(read_field(market, "connector", "")).strip().casefold()
    market_id = str(read_field(market, "market_id", "")).strip().casefold()

    if market_id:
        return connector, "market_id", market_id

    platform = str(read_field(market, "platform", "")).strip().casefold()
    question = str(read_field(market, "question", "")).strip().casefold()
    return connector, platform, question


def duplicate_identities(markets: list[Any]) -> list[tuple[str, str, str]]:
    seen: set[tuple[str, str, str]] = set()
    duplicates: list[tuple[str, str, str]] = []

    for market in markets:
        identity = market_identity(market)
        if identity in seen:
            duplicates.append(identity)
        else:
            seen.add(identity)

    return duplicates


def opportunity_route(opportunity: Mapping[str, Any]) -> tuple[str, str, str]:
    question = str(opportunity.get("question", "")).strip().casefold()
    yes_platform = str(
        opportunity.get("buy_yes_platform", "")
    ).strip().casefold()
    no_platform = str(
        opportunity.get("buy_no_platform", "")
    ).strip().casefold()
    return question, yes_platform, no_platform


def main() -> int:
    report = TestReport()
    app = create_app()

    update_events: list[dict[str, Any]] = []
    update_lock = threading.RLock()

    def collect_market_update(event: Any) -> None:
        payload = getattr(event, "payload", {})
        if not isinstance(payload, Mapping):
            payload = {"raw": str(payload)}

        with update_lock:
            update_events.append(
                {
                    "created_at": getattr(
                        event,
                        "created_at",
                        datetime.now(timezone.utc),
                    ).isoformat(),
                    "payload": dict(payload),
                }
            )

    event_bus.subscribe(MARKET_UPDATED_EVENT, collect_market_update)

    try:
        report.run(
            "Guardas de segurança",
            lambda: {
                "mock": settings.MOCK_CONNECTOR_ENABLED,
                "hyperliquid": settings.HYPERLIQUID_CONNECTOR_ENABLED,
                "scheduler": settings.SCHEDULER_ENABLED,
                "interval_seconds": settings.MARKET_UPDATE_INTERVAL_SECONDS,
                "execution_worker": settings.EXECUTION_WORKER_ENABLED,
                "ai_execution_authorized": settings.AI_EXECUTION_AUTHORIZED,
                "model_auto_load": settings.AI_AUTO_LOAD_MODEL,
            }
            if (
                settings.MOCK_CONNECTOR_ENABLED
                and settings.HYPERLIQUID_CONNECTOR_ENABLED
                and settings.SCHEDULER_ENABLED
                and not settings.EXECUTION_WORKER_ENABLED
                and not settings.AI_EXECUTION_AUTHORIZED
                and not settings.AI_AUTO_LOAD_MODEL
            )
            else (_ for _ in ()).throw(
                AssertionError("As guardas da Fase 3 não estão ativas.")
            ),
        )

        with TestClient(app) as client:
            def check_startup() -> dict[str, Any]:
                response = client.get("/health")
                data = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(data.get("status") == "healthy", f"Health inválido: {data}")
                require(data.get("startup_error") is None, f"Startup error: {data}")
                lifecycle = data.get("lifecycle", {})
                require(lifecycle.get("connectors") is True, "Connectors não iniciaram.")
                require(lifecycle.get("scheduler") is True, "Scheduler não iniciou.")
                require(lifecycle.get("execution_worker") is False, "Worker foi iniciado.")
                configuration = data.get("connector_configuration", {})
                require(configuration.get("mock_enabled") is True, "Mock desabilitado.")
                require(
                    configuration.get("hyperliquid_enabled") is True,
                    "Hyperliquid desabilitada.",
                )
                require(
                    data.get("ai", {}).get("execution_authorized") is False,
                    "AI autorizou execução.",
                )
                return data

            report.run("Startup e lifecycle", check_startup)

            def check_connectors() -> dict[str, Any]:
                names_response = client.get("/connectors/")
                names = names_response.json()
                require(names_response.status_code == 200, f"HTTP {names_response.status_code}")
                require(
                    set(names) == {"mock", "hyperliquid"},
                    f"Connectors inesperados: {names}",
                )

                health_response = client.get("/connectors/health")
                health = health_response.json()
                require(health_response.status_code == 200, f"HTTP {health_response.status_code}")
                require(health.get("registered") == 2, f"Registrados: {health}")
                require(health.get("online") == 2, f"Conector offline: {health}")
                require(health.get("errors") == 0, f"Erro de connector: {health}")
                return {"names": names, "health": health}

            report.run("Dois connectors online", check_connectors)

            def check_initial_repository() -> dict[str, Any]:
                response = client.get("/markets/")
                markets = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(isinstance(markets, list), "Markets não retornou lista.")
                require(len(markets) >= 5, f"Repository com poucos mercados: {len(markets)}")

                mock_markets = [
                    item for item in markets if item.get("connector") == "mock"
                ]
                hyperliquid_markets = [
                    item
                    for item in markets
                    if item.get("connector") == "hyperliquid"
                ]

                require(len(mock_markets) == 5, f"Mock deveria ter 5 mercados: {len(mock_markets)}")
                duplicates = duplicate_identities(markets)
                require(not duplicates, f"Mercados duplicados: {duplicates[:5]}")

                if not hyperliquid_markets:
                    report.warn(
                        "Nenhum mercado HIP-4 ativo foi normalizado no snapshot inicial; "
                        "o conector permaneceu online e o scheduler continuará sendo testado."
                    )

                return {
                    "total": len(markets),
                    "mock": len(mock_markets),
                    "hyperliquid": len(hyperliquid_markets),
                    "repository": market_repository.status(),
                }

            initial_repository = report.run(
                "Repository inicial e deduplicação",
                check_initial_repository,
            )

            def check_scheduler() -> dict[str, Any]:
                response = client.get("/health")
                data = response.json()
                scheduler = data.get("scheduler", {})
                require(scheduler.get("enabled") is True, f"Scheduler desabilitado: {scheduler}")
                require(scheduler.get("running") is True, f"Scheduler parado: {scheduler}")
                require(scheduler.get("jobs") == 1, f"Jobs inesperados: {scheduler}")
                require(
                    scheduler.get("job_ids") == ["market_update_task"],
                    f"Job incorreto: {scheduler}",
                )
                return scheduler

            report.run("Scheduler e job único", check_scheduler)

            def observe_cycles() -> dict[str, Any]:
                with update_lock:
                    baseline_event_count = len(update_events)

                deadline = time.monotonic() + OBSERVATION_SECONDS
                repository_snapshots: list[dict[str, Any]] = []

                while time.monotonic() < deadline:
                    status_response = client.get("/connectors/status")
                    require(
                        status_response.status_code == 200,
                        f"HTTP {status_response.status_code}",
                    )
                    status = status_response.json()
                    repository_snapshots.append(
                        {
                            "observed_at": datetime.now(timezone.utc).isoformat(),
                            "repository": status.get("repository", {}),
                            "connectors": status.get("connectors", {}),
                        }
                    )

                    with update_lock:
                        new_events = len(update_events) - baseline_event_count

                    if new_events >= 2:
                        # Captura um snapshot após o segundo evento para evitar
                        # que a última atualização ocorra entre duas leituras.
                        final_status = client.get("/connectors/status").json()
                        repository_snapshots.append(
                            {
                                "observed_at": datetime.now(timezone.utc).isoformat(),
                                "repository": final_status.get("repository", {}),
                                "connectors": final_status.get("connectors", {}),
                            }
                        )
                        break

                    time.sleep(1.0)

                with update_lock:
                    observed_events = list(update_events[baseline_event_count:])

                require(
                    len(observed_events) >= 2,
                    "O scheduler não publicou duas atualizações dentro do período observado.",
                )

                event_statuses = [
                    str(item.get("payload", {}).get("status", ""))
                    for item in observed_events
                ]
                require(
                    all(status in {"success", "partial"} for status in event_statuses),
                    f"Atualização com status inválido: {event_statuses}",
                )

                partial_count = sum(status == "partial" for status in event_statuses)
                if partial_count:
                    report.warn(
                        f"Foram observadas {partial_count} atualizações parciais; "
                        "consulte os detalhes dos connectors no relatório."
                    )

                update_times = {
                    snapshot.get("repository", {}).get("updated_at")
                    for snapshot in repository_snapshots
                    if snapshot.get("repository", {}).get("updated_at")
                }
                require(
                    len(update_times) >= 2,
                    f"updated_at não avançou em ciclos distintos: {sorted(update_times)}",
                )

                return {
                    "baseline_events": baseline_event_count,
                    "scheduled_events": len(observed_events),
                    "event_statuses": event_statuses,
                    "distinct_repository_updates": len(update_times),
                    "repository_snapshots": repository_snapshots,
                    "events": observed_events,
                }

            report.run("Dois ciclos reais do scheduler", observe_cycles)

            def check_replacement_stability() -> dict[str, Any]:
                markets = market_repository.all()
                duplicates = duplicate_identities(markets)
                require(not duplicates, f"Duplicações após scheduler: {duplicates[:5]}")

                connector_statuses: dict[str, Any] = {}
                expected_count = -1

                # O scheduler pode iniciar um novo ciclo entre duas leituras.
                # Fazemos até três snapshots curtos e aceitamos o primeiro
                # estado consistente entre repository e status dos connectors.
                for _ in range(3):
                    statuses = client.get("/connectors/status").json()
                    connector_statuses = statuses.get("connectors", {})
                    markets = market_repository.all()
                    expected_count = sum(
                        int(status.get("markets") or 0)
                        for status in connector_statuses.values()
                    )
                    if len(markets) == expected_count:
                        break
                    time.sleep(0.25)

                errors = {
                    name: status.get("error")
                    for name, status in connector_statuses.items()
                    if status.get("error")
                }
                require(not errors, f"Connectors com erro após scheduler: {errors}")
                require(
                    len(markets) == expected_count,
                    "Repository não corresponde à soma do último lote dos connectors: "
                    f"repository={len(markets)} connectors={expected_count}",
                )

                mock_count = sum(
                    1 for market in markets if read_field(market, "connector") == "mock"
                )
                require(mock_count == 5, f"Mock acumulou/perdeu mercados: {mock_count}")

                return {
                    "initial_repository": initial_repository,
                    "final_repository": market_repository.status(),
                    "expected_from_connectors": expected_count,
                    "duplicates": len(duplicates),
                    "connector_statuses": connector_statuses,
                }

            report.run("Substituição atômica sem acúmulo", check_replacement_stability)

            def check_manual_refreshes() -> dict[str, Any]:
                snapshots: list[dict[str, Any]] = []

                for index in range(2):
                    response = client.post("/connectors/refresh")
                    data = response.json()
                    require(response.status_code == 200, f"HTTP {response.status_code}: {data}")
                    require(data.get("status") == "completed", f"Refresh {index + 1}: {data}")

                    markets = market_repository.all()
                    duplicates = duplicate_identities(markets)
                    require(
                        not duplicates,
                        f"Refresh {index + 1} gerou duplicações: {duplicates[:5]}",
                    )
                    require(
                        int(data.get("markets", -1)) == len(markets),
                        f"Refresh {index + 1} divergiu do repository.",
                    )
                    snapshots.append(
                        {
                            "refresh": index + 1,
                            "markets": len(markets),
                            "repository": market_repository.status(),
                            "connectors": data.get("connectors", {}),
                        }
                    )

                return {"snapshots": snapshots}

            report.run("Refresh manual repetido e idempotente", check_manual_refreshes)

            def check_opportunities() -> dict[str, Any]:
                response = client.get("/opportunities/")
                opportunities = response.json()
                require(response.status_code == 200, f"HTTP {response.status_code}")
                require(isinstance(opportunities, list), "Opportunities não retornou lista.")

                routes: list[tuple[str, str, str]] = []
                hyperliquid_routes = 0

                for opportunity in opportunities:
                    require(isinstance(opportunity, Mapping), "Oportunidade inválida.")
                    route = opportunity_route(opportunity)
                    require(route[1] and route[2], f"Rota incompleta: {opportunity}")
                    require(route[1] != route[2], f"Rota na mesma plataforma: {opportunity}")
                    routes.append(route)

                    if "hyperliquid" in {route[1], route[2]}:
                        hyperliquid_routes += 1

                    ai_analysis = opportunity.get("ai_analysis")
                    if isinstance(ai_analysis, Mapping):
                        require(
                            ai_analysis.get("execution_authorized") is False,
                            "AI autorizou execução em uma oportunidade.",
                        )

                require(
                    len(routes) == len(set(routes)),
                    "O comparator retornou rotas duplicadas.",
                )

                if not opportunities:
                    report.warn(
                        "Nenhuma oportunidade foi aprovada neste snapshot; "
                        "isso não invalida a estabilidade dos dados reais."
                    )
                elif hyperliquid_routes == 0:
                    report.warn(
                        "As oportunidades atuais não utilizam uma perna Hyperliquid; "
                        "a compatibilidade de perguntas reais pode não ter ocorrido neste momento."
                    )

                pipeline = client.get("/opportunities/pipeline").json()
                require(
                    all(name in pipeline.get("pipelines", {}) for name in ("analysis", "paper", "live")),
                    f"Pipelines incompletos: {pipeline}",
                )

                return {
                    "opportunities": len(opportunities),
                    "unique_routes": len(set(routes)),
                    "hyperliquid_routes": hyperliquid_routes,
                    "sample": opportunities[0] if opportunities else None,
                    "pipeline": pipeline,
                }

            report.run("Comparação cross-platform sem rotas duplicadas", check_opportunities)

            def check_dashboard() -> dict[str, Any]:
                snapshot_response = client.get("/dashboard/api/snapshot")
                snapshot = snapshot_response.json()
                require(snapshot_response.status_code == 200, f"HTTP {snapshot_response.status_code}")
                require(snapshot.get("status") in {"ONLINE", "DEGRADED"}, f"Dashboard: {snapshot}")
                require(
                    int(snapshot.get("markets", -1)) == market_repository.count(),
                    "Dashboard divergiu do MarketRepository.",
                )

                health = client.get("/health").json()
                require(health.get("ai", {}).get("advisory_only") is True, "AI não está consultiva.")
                require(
                    health.get("ai", {}).get("execution_authorized") is False,
                    "AI autorizou execução.",
                )

                return {
                    "dashboard_status": snapshot.get("status"),
                    "markets": snapshot.get("markets"),
                    "opportunities": snapshot.get("opportunities"),
                    "diagnostics": snapshot.get("diagnostics"),
                    "ai": health.get("ai"),
                }

            report.run("Dashboard e AI consultiva", check_dashboard)

        def check_live_guard() -> dict[str, Any]:
            calls: list[Any] = []

            def real_executor(order: Any) -> dict[str, Any]:
                calls.append(order)
                return {"accepted": True}

            engine = ExecutionEngine(executor=real_executor)
            result = engine.execute({"id": "phase3-live-guard"})
            require(result.get("status") == "DISABLED", f"Live não bloqueado: {result}")
            require(result.get("executed") is False, f"Execução marcada como realizada: {result}")
            require(calls == [], f"Executor foi chamado: {calls}")
            return {"result": result, "executor_calls": len(calls)}

        report.run("Proteção de execução live", check_live_guard)

        report.run(
            "Shutdown limpo do scheduler",
            lambda: scheduler_service.status()
            if not scheduler_service.running
            else (_ for _ in ()).throw(
                AssertionError(f"Scheduler permaneceu ativo: {scheduler_service.status()}")
            ),
        )

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

    finally:
        event_bus.unsubscribe(MARKET_UPDATED_EVENT, collect_market_update)

    payload = report.finish()
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print()
    print("=" * 76)
    print("PREDARB — TESTE REAL / FASE 3: SCHEDULER E ESTABILIDADE")
    print("=" * 76)
    print(f"Aprovados: {payload['summary']['passed']}")
    print(f"Falhas:    {payload['summary']['failed']}")
    print(f"Avisos:    {payload['summary']['warnings']}")
    print(f"Relatório: {REPORT_PATH}")

    return 0 if payload["summary"]["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
