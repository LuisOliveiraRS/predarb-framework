from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORT_PATH = BACKEND_ROOT / "real_test_reports" / "phase6_server_session_report.json"


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

    def finish(self, details: dict[str, Any]) -> int:
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
            "details": details,
        }
        REPORT_PATH.write_text(
            json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print()
        print(f"Aprovados: {report['summary']['passed']}")
        print(f"Falhas:    {report['summary']['failed']}")
        print(f"Relatório: {REPORT_PATH}")
        return 1 if self.failures else 0


def request(client: httpx.Client, method: str, path: str, **kwargs: Any) -> Any:
    response = client.request(method, path, **kwargs)
    response.raise_for_status()
    return response.json()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--cycles", type=int, default=12)
    parser.add_argument("--interval-seconds", type=float, default=0.25)
    args = parser.parse_args()

    audit = Audit()
    with httpx.Client(base_url=args.base_url, timeout=30.0) as client:
        health = request(client, "GET", "/health")
        paper_status = request(client, "GET", "/paper/status")
        audit.check(
            "Servidor Paper seguro",
            health.get("status") == "healthy"
            and health.get("lifecycle", {}).get("execution_worker") is False
            and health.get("ai", {}).get("execution_authorized") is False
            and paper_status.get("enabled") is True
            and paper_status.get("execution_authorized") is False
            and paper_status.get("live_execution") is False,
            {"health": health, "paper": paper_status},
        )

        reset = request(
            client,
            "POST",
            "/paper/reset",
            params={"confirm": "RESET-PAPER", "persist": "true"},
        )
        audit.check(
            "Conta Paper resetada",
            reset.get("trade_count") == 0 and reset.get("open_positions") == 0,
            reset,
        )

        for cycle in range(1, args.cycles + 1):
            price = round(0.30 + (cycle % 6) * 0.05, 4)
            quantity = 10 + cycle
            order_id = f"phase6-http-order-{cycle:03d}"
            symbol = f"PHASE6-HTTP-{cycle:03d}"
            payload = {
                "execution_id": f"phase6-http-execution-{cycle:03d}",
                "persist": True,
                "orders": [
                    {
                        "id": order_id,
                        "opportunity_id": f"phase6-http-opp-{cycle:03d}",
                        "platform": "http-paper",
                        "symbol": symbol,
                        "market": f"Paper HTTP {cycle:03d}",
                        "leg": "YES" if cycle % 2 else "NO",
                        "side": "BUY",
                        "quantity": quantity,
                        "price": price,
                    }
                ],
                "reports": [
                    {
                        "order_id": order_id,
                        "status": "FILLED",
                        "mode": "PAPER",
                        "platform": "http-paper",
                        "symbol": symbol,
                        "leg": "YES" if cycle % 2 else "NO",
                        "side": "BUY",
                        "filled_quantity": quantity,
                        "average_price": price,
                        "gross_notional": round(quantity * price, 8),
                        "fee": round(quantity * price * 0.001, 8),
                    }
                ],
            }
            committed = request(client, "POST", "/paper/commit", json=payload)
            account = committed["account"]
            open_positions = [
                item for item in account.get("positions", []) if item.get("status") == "OPEN"
            ]
            marks = {
                item["id"]: round(
                    min(0.95, max(0.05, float(item["average_price"]) + (0.04 if cycle % 2 else -0.025))),
                    4,
                )
                for item in open_positions
            }
            request(
                client,
                "POST",
                "/paper/mark",
                json={"prices": marks, "persist": cycle % 3 == 0},
            )
            if args.interval_seconds > 0:
                time.sleep(args.interval_seconds)

        account = request(client, "GET", "/paper/account")
        equity = request(client, "GET", "/paper/equity", params={"limit": 2000})
        statistics = request(client, "GET", "/paper/statistics")
        dashboard = request(client, "GET", "/dashboard/api/snapshot", params={"refresh": "true"})
        dashboard_paper = dashboard.get("data", {}).get("paper", {})

        audit.check(
            "Sessão HTTP persistente concluída",
            account.get("trade_count") == args.cycles
            and account.get("open_positions") == args.cycles
            and account.get("processed_orders") == args.cycles,
            {
                "cycles": args.cycles,
                "trades": account.get("trade_count"),
                "positions": account.get("open_positions"),
            },
        )
        audit.check(
            "Curva HTTP disponível",
            len(equity.get("curve", [])) >= args.cycles * 2
            and equity.get("analytics", {}).get("points") == len(equity.get("curve", [])),
            equity,
        )
        audit.check(
            "Estatísticas Paper consistentes",
            statistics.get("equity") == account.get("equity")
            and statistics.get("trade_count") == account.get("trade_count")
            and statistics.get("execution_authorized") is False
            and statistics.get("live_execution") is False,
            statistics,
        )
        audit.check(
            "Dashboard sincronizado com a conta Paper",
            dashboard_paper.get("account_id") == account.get("account_id")
            and dashboard_paper.get("trade_count") == account.get("trade_count")
            and dashboard_paper.get("equity") == account.get("equity")
            and len(dashboard_paper.get("equity_curve", [])) == len(account.get("equity_curve", [])),
            {
                "account": {
                    "id": account.get("account_id"),
                    "trades": account.get("trade_count"),
                    "equity": account.get("equity"),
                    "points": len(account.get("equity_curve", [])),
                },
                "dashboard": {
                    "id": dashboard_paper.get("account_id"),
                    "trades": dashboard_paper.get("trade_count"),
                    "equity": dashboard_paper.get("equity"),
                    "points": len(dashboard_paper.get("equity_curve", [])),
                },
            },
        )
        audit.check(
            "Proteções operacionais mantidas",
            account.get("execution_authorized") is False
            and account.get("live_execution") is False
            and health.get("lifecycle", {}).get("execution_worker") is False
            and health.get("ai", {}).get("execution_authorized") is False,
            {
                "account_execution": account.get("execution_authorized"),
                "account_live": account.get("live_execution"),
                "worker": health.get("lifecycle", {}).get("execution_worker"),
                "ai_execution": health.get("ai", {}).get("execution_authorized"),
            },
        )
        request(client, "POST", "/paper/save")

        return audit.finish(
            {
                "base_url": args.base_url,
                "cycles": args.cycles,
                "account": account,
                "equity": equity,
                "statistics": statistics,
                "dashboard_paper": dashboard_paper,
            }
        )


if __name__ == "__main__":
    raise SystemExit(main())
