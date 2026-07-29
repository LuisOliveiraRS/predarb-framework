from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import httpx

BACKEND_ROOT = Path(__file__).resolve().parents[2]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from app.market.comparators.cross_platform import CrossPlatformComparator

REPORT_DIR = BACKEND_ROOT / "real_test_reports"
REPORT_PATH = REPORT_DIR / "phase7_server_session_report.json"


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
        finished = datetime.now(timezone.utc)
        passed = sum(item["status"] == "PASS" for item in self.checks)
        failed = sum(item["status"] == "FAIL" for item in self.checks)
        return {
            "test": "PredArb Phase 7 - Server Paper Session",
            "started_at": self.started_at.isoformat(),
            "finished_at": finished.isoformat(),
            "duration_seconds": round((finished - self.started_at).total_seconds(), 3),
            "summary": {"passed": passed, "failed": failed, "total": len(self.checks)},
            "checks": self.checks,
            "execution_authorized": False,
            "live_execution": False,
        }


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)


def controlled_opportunity() -> dict[str, Any]:
    values = CrossPlatformComparator().compare(
        [
            {
                "platform": "Phase7-Control-A",
                "question": "Will the Phase 7 HTTP risk probe pass?",
                "yes": 0.40,
                "no": 0.60,
                "liquidity": 10_000,
                "volume": 10_000,
                "market_id": "phase7-http-a",
            },
            {
                "platform": "Phase7-Control-B",
                "question": "Will the Phase 7 HTTP risk probe pass?",
                "yes": 0.55,
                "no": 0.45,
                "liquidity": 10_000,
                "volume": 10_000,
                "market_id": "phase7-http-b",
            },
        ]
    )
    require(bool(values), "O comparator não gerou a oportunidade de controle.")
    return values[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:8000")
    parser.add_argument("--wait-seconds", type=int, default=25)
    args = parser.parse_args()
    base_url = args.base_url.rstrip("/")
    report = Report()

    with httpx.Client(base_url=base_url, timeout=45.0) as client:
        def health_check() -> dict[str, Any]:
            response = client.get("/health")
            response.raise_for_status()
            data = response.json()
            require(data.get("status") == "healthy", f"Health inválido: {data}")
            config = data.get("connector_configuration", {})
            require(config.get("mock_enabled") is True, "MockConnector está desligado.")
            require(
                config.get("hyperliquid_enabled") is True,
                "HyperliquidConnector está desligado.",
            )
            lifecycle = data.get("lifecycle", {})
            require(lifecycle.get("execution_worker") is False, "Worker live está ativo.")
            ai = data.get("ai", {})
            require(ai.get("execution_authorized") is False, "AI autorizou execução.")
            session = data.get("paper_session", {})
            require(session.get("enabled") is True, "Sessão Paper está desabilitada.")
            require(session.get("auto_start") is False, "Auto start Paper está ativo.")
            return {
                "connector_configuration": config,
                "scheduler": data.get("scheduler"),
                "paper_session": session,
                "ai": ai,
            }

        report.run("Servidor e guardas de segurança", health_check)

        def prepare() -> dict[str, Any]:
            account = client.post(
                "/paper/reset", params={"confirm": "RESET-PAPER", "persist": "true"}
            )
            account.raise_for_status()
            session = client.post(
                "/paper/session/reset-report",
                params={"confirm": "RESET-PAPER-SESSION-REPORT"},
            )
            session.raise_for_status()
            refresh = client.post("/connectors/refresh")
            refresh.raise_for_status()
            return {
                "account": account.json(),
                "session": session.json(),
                "refresh": refresh.json(),
            }

        report.run("Ambiente Paper resetado", prepare)

        def real_signal_cycle() -> dict[str, Any]:
            opportunities = client.get("/opportunities/")
            opportunities.raise_for_status()
            values = opportunities.json()
            cycle = client.post("/paper/session/cycle", json={})
            cycle.raise_for_status()
            payload = cycle.json()
            require(
                payload.get("status")
                in {"SUCCESS", "NO_SIGNAL", "RISK_REJECTED", "RISK_STOPPED"},
                f"Status inesperado do ciclo real: {payload}",
            )
            return {
                "real_opportunities": len(values) if isinstance(values, list) else 0,
                "cycle": payload,
            }

        report.run("Ciclo com fonte real", real_signal_cycle)

        def automated_runtime() -> dict[str, Any]:
            before = client.get("/paper/session/report").json().get("total_cycles", 0)
            started = client.post(
                "/paper/session/start", params={"confirm": "START-PAPER-SESSION"}
            )
            started.raise_for_status()
            require(started.json().get("running") is True, "Runtime não iniciou.")

            deadline = time.monotonic() + max(5, args.wait_seconds)
            latest: dict[str, Any] = {}
            while time.monotonic() < deadline:
                latest = client.get("/paper/session/status").json()
                total = latest.get("session", {}).get("total_cycles", 0)
                if total > before:
                    break
                time.sleep(1)

            stopped = client.post("/paper/session/stop")
            stopped.raise_for_status()
            after = client.get("/paper/session/report").json()
            require(after.get("total_cycles", 0) > before, "Nenhum ciclo automatizado ocorreu.")
            require(stopped.json().get("running") is False, "Runtime não encerrou.")
            return {"before": before, "after": after.get("total_cycles"), "status": latest}

        report.run("Runtime automatizado explícito", automated_runtime)

        def controlled_risk_probe() -> dict[str, Any]:
            client.post(
                "/paper/reset", params={"confirm": "RESET-PAPER", "persist": "true"}
            ).raise_for_status()
            client.post(
                "/paper/session/reset-report",
                params={"confirm": "RESET-PAPER-SESSION-REPORT"},
            ).raise_for_status()
            opportunity = controlled_opportunity()
            first = client.post(
                "/paper/session/cycle", json={"opportunities": [opportunity]}
            )
            first.raise_for_status()
            first_payload = first.json()
            require(first_payload.get("status") == "SUCCESS", f"Primeiro ciclo: {first_payload}")
            require(first_payload.get("orders") == 2, "Primeiro ciclo sem duas ordens.")
            require(first_payload.get("fills") == 2, "Primeiro ciclo sem dois fills.")

            second = client.post(
                "/paper/session/cycle", json={"opportunities": [opportunity]}
            )
            second.raise_for_status()
            second_payload = second.json()
            require(
                second_payload.get("status") == "RISK_REJECTED",
                f"Segundo ciclo deveria ser rejeitado: {second_payload}",
            )
            codes = {
                code
                for item in second_payload.get("risk", {}).get("rejections", [])
                for code in item.get("codes", [])
            }
            require("MARKET_EXPOSURE_LIMIT" in codes, f"Código ausente: {codes}")
            return {
                "first": first_payload,
                "second_status": second_payload.get("status"),
                "codes": sorted(codes),
            }

        report.run("Limites de risco via HTTP", controlled_risk_probe)

        def final_report() -> dict[str, Any]:
            session = client.get("/paper/session/report")
            session.raise_for_status()
            risk = client.get("/paper/risk/status")
            risk.raise_for_status()
            account = client.get("/paper/account", params={"include_trades": "false"})
            account.raise_for_status()
            values = {
                "session": session.json(),
                "risk": risk.json(),
                "account": account.json(),
            }
            require(values["session"].get("execution_authorized") is False, "Sessão autorizou live.")
            require(values["risk"].get("execution_authorized") is False, "Risco autorizou live.")
            require(values["account"].get("live_execution") is False, "Conta marcou live.")
            return values

        report.run("Relatório de desempenho e isolamento", final_report)

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
