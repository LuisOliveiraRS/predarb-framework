from __future__ import annotations

import argparse
import json
import os
import sys
import time
import traceback
from collections.abc import Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

# Este processo apenas consome snapshots HTTP e executa o Pipeline paper local.
os.environ.update(
    {
        "MOCK_CONNECTOR_ENABLED": "false",
        "HYPERLIQUID_CONNECTOR_ENABLED": "false",
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
    }
)

import httpx

from app.market.comparators.cross_platform import CrossPlatformComparator
from app.orders.fill_repository import fill_repository
from app.orders.order_repository import order_repository
from app.paper.paper_trade_history import paper_trade_history
from app.paper.paper_wallet import paper_wallet
from app.pipeline.pipeline_builder import PipelineBuilder
from app.positions.position_repository import position_repository
from app.trading.trade_repository import trade_repository


REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase4_server_paper_probe_report.json"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def read_field(target: Any, name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(name, default)
    return getattr(target, name, default)


def repository_snapshot() -> dict[str, Any]:
    return {
        "orders": order_repository.count(),
        "fills": fill_repository.count(),
        "trades": trade_repository.count(),
        "positions": len(list(position_repository.all() or [])),
        "paper_history": len(list(paper_trade_history.all() or [])),
        "paper_wallet_balance": float(paper_wallet.balance),
        "paper_wallet_locked": float(paper_wallet.locked),
    }


def choose_hyperliquid_market(markets: list[dict[str, Any]]) -> dict[str, Any]:
    candidates: list[dict[str, Any]] = []
    for market in markets:
        if str(market.get("connector", "")).strip().casefold() != "hyperliquid":
            continue
        try:
            yes = float(market.get("yes"))
            no = float(market.get("no"))
        except (TypeError, ValueError):
            continue
        if str(market.get("question", "")).strip() and 0 < yes < 1 and 0 < no < 1:
            candidates.append(market)

    require(bool(candidates), "Nenhum mercado Hyperliquid válido foi encontrado no servidor.")
    candidates.sort(key=lambda item: abs(min(float(item["yes"]), float(item["no"])) - 0.5))
    return candidates[0]


def build_control_market(live_market: Mapping[str, Any]) -> dict[str, Any]:
    yes = float(live_market["yes"])
    no = float(live_market["no"])
    target_cost = 0.90

    if yes <= no:
        control_no = target_cost - yes
        require(0 < control_no < 1, "Perna No controlada inválida.")
        control_yes = 1 - control_no
    else:
        control_yes = target_cost - no
        require(0 < control_yes < 1, "Perna Yes controlada inválida.")
        control_no = 1 - control_yes

    liquidity = max(
        10_000.0,
        float(live_market.get("liquidity") or 0),
        float(live_market.get("volume") or 0),
    )
    source_id = str(live_market.get("market_id") or "unknown")

    return {
        "platform": "Phase4PaperControl",
        "question": str(live_market.get("question", "")).strip(),
        "yes": round(control_yes, 6),
        "no": round(control_no, 6),
        "created_at": datetime.now(timezone.utc).isoformat(),
        "connector": "phase4_control",
        "liquidity": liquidity,
        "volume": liquidity,
        "fee": 0.0,
        "market_id": f"phase4-control:{source_id}",
        "category": str(live_market.get("category") or ""),
        "asset": str(live_market.get("asset") or ""),
        "event_type": str(live_market.get("event_type") or ""),
        "expires_at": live_market.get("expires_at"),
        "status": "open",
        "metadata": {
            "simulated": True,
            "paper_only": True,
            "source_connector": "hyperliquid",
            "source_market_id": source_id,
            "target_cost": target_cost,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cycles", type=int, default=3)
    parser.add_argument("--interval-seconds", type=float, default=5.0)
    args = parser.parse_args()

    base_url = args.base_url.rstrip("/")
    cycles = max(1, args.cycles)
    interval = max(0.0, args.interval_seconds)
    started_at = datetime.now(timezone.utc)
    checks: list[dict[str, Any]] = []
    snapshots: list[dict[str, Any]] = []
    all_order_ids: set[str] = set()
    before = repository_snapshot()

    try:
        with httpx.Client(base_url=base_url, timeout=45.0) as client:
            health_response = client.get("/health")
            health_response.raise_for_status()
            health = health_response.json()
            require(health.get("status") == "healthy", f"Health inesperado: {health}")
            configuration = health.get("connector_configuration", {})
            require(configuration.get("mock_enabled") is True, "Servidor não está com MockConnector.")
            require(configuration.get("hyperliquid_enabled") is True, "Servidor não está com HyperliquidConnector.")
            require(health.get("scheduler", {}).get("running") is True, "Scheduler do servidor não está ativo.")
            require(health.get("lifecycle", {}).get("execution_worker") is False, "Execution Worker está ativo.")
            require(health.get("ai", {}).get("execution_authorized") is False, "AI autorizou execução.")
            checks.append({"name": "Servidor seguro", "status": "PASS", "details": health})
            print("[PASS] Servidor seguro")

            pipeline = PipelineBuilder().build_paper(paper_fee_rate=0.001)
            comparator = CrossPlatformComparator()

            for cycle in range(1, cycles + 1):
                markets_response = client.get("/markets/")
                markets_response.raise_for_status()
                markets = markets_response.json()
                require(isinstance(markets, list), "Resposta /markets/ não é lista.")
                require(len(markets) >= 5, "Repository HTTP possui menos de cinco mercados.")

                live_market = choose_hyperliquid_market(markets)
                control_market = build_control_market(live_market)
                opportunities = comparator.compare([live_market, control_market])
                require(opportunities, f"Ciclo {cycle}: comparator não criou oportunidade.")

                result = pipeline.execute(deepcopy(opportunities))
                require(result.success, f"Ciclo {cycle}: Pipeline paper falhou: {result.errors}")
                summary = result.output
                require(summary.get("status") == "SUCCESS", f"Ciclo {cycle}: {summary}")
                require(summary.get("orders_received") == 2, f"Ciclo {cycle}: ordens inválidas.")
                require(summary.get("orders_filled") == 2, f"Ciclo {cycle}: fills inválidos.")
                require(float(summary.get("total_fees", 0)) > 0, f"Ciclo {cycle}: fees não calculadas.")

                order_ids = {
                    str(read_field(order, "id", ""))
                    for order in list(result.context.orders or [])
                    if str(read_field(order, "id", ""))
                }
                require(len(order_ids) == 2, f"Ciclo {cycle}: IDs de ordem inválidos.")
                require(not all_order_ids.intersection(order_ids), f"Ciclo {cycle}: IDs reutilizados.")
                all_order_ids.update(order_ids)

                snapshots.append(
                    {
                        "cycle": cycle,
                        "server_markets": len(markets),
                        "mock_markets": sum(
                            str(item.get("connector", "")).casefold() == "mock"
                            for item in markets
                        ),
                        "hyperliquid_markets": sum(
                            str(item.get("connector", "")).casefold() == "hyperliquid"
                            for item in markets
                        ),
                        "source_market": live_market,
                        "control_market": control_market,
                        "paper_summary": summary,
                        "order_ids": sorted(order_ids),
                    }
                )
                print(
                    f"[PASS] Ciclo {cycle}/{cycles}: "
                    f"markets={len(markets)} orders=2 fills=2 fees={summary.get('total_fees')}"
                )

                if cycle < cycles and interval:
                    time.sleep(interval)

            checks.append(
                {
                    "name": "Replay paper via servidor",
                    "status": "PASS",
                    "details": {
                        "cycles": cycles,
                        "unique_order_ids": len(all_order_ids),
                    },
                }
            )

        after = repository_snapshot()
        require(after == before, f"Paper local alterou repositórios globais: before={before}, after={after}")
        checks.append(
            {
                "name": "Isolamento local",
                "status": "PASS",
                "details": {"before": before, "after": after},
            }
        )
        print("[PASS] Isolamento local")
        error = None

    except Exception as exc:
        error = str(exc)
        checks.append(
            {
                "name": "Execução da sonda",
                "status": "FAIL",
                "error": error,
                "traceback": traceback.format_exc(),
            }
        )
        print(f"[FAIL] {error}")

    finished_at = datetime.now(timezone.utc)
    failed = sum(item.get("status") == "FAIL" for item in checks)
    passed = sum(item.get("status") == "PASS" for item in checks)
    payload = {
        "test": "PredArb Phase 4 - Server Paper Probe",
        "started_at": started_at.isoformat(),
        "finished_at": finished_at.isoformat(),
        "duration_seconds": round((finished_at - started_at).total_seconds(), 3),
        "environment": {
            "base_url": base_url,
            "cycles": cycles,
            "interval_seconds": interval,
            "paper_fee_rate": 0.001,
            "execution_worker_required": False,
            "ai_execution_authorized_required": False,
        },
        "summary": {
            "passed": passed,
            "failed": failed,
            "cycles_completed": len(snapshots),
            "unique_order_ids": len(all_order_ids),
        },
        "checks": checks,
        "cycles": snapshots,
        "error": error,
    }
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )

    print()
    print("=" * 72)
    print("PREDARB — FASE 4 — SONDA PAPER VIA SERVIDOR")
    print("=" * 72)
    print(f"Aprovados: {passed}")
    print(f"Falhas:    {failed}")
    print(f"Ciclos:    {len(snapshots)}/{cycles}")
    print(f"Relatório: {REPORT_PATH}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
