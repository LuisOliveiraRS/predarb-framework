from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Mapping


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPORT_DIR = BACKEND_ROOT / "real_test_reports"


def latest_report() -> Path:
    values = sorted(
        REPORT_DIR.glob(
            "phase8_long_session_*.json"
        ),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    )

    if not values:
        raise FileNotFoundError(
            "Nenhum relatório da Fase 8 foi encontrado."
        )

    return values[0]


def read_report(
    path: Path,
) -> Mapping[str, Any]:
    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    if not isinstance(payload, dict):
        raise ValueError(
            "Relatório JSON inválido."
        )

    return payload


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
    )

    args = parser.parse_args()

    path = (
        args.path.resolve()
        if args.path
        else latest_report()
    )

    report = read_report(path)
    summary = report.get("summary") or {}
    performance = report.get("performance") or {}

    print("PredArb - Resumo da Fase 8")
    print("=" * 60)
    print("Arquivo:", path)
    print("Status:", summary.get("status"))
    print("Amostras:", summary.get("samples"))
    print(
        "Ciclos:",
        performance.get("cycles_delta"),
    )
    print(
        "Sucessos:",
        performance.get(
            "successful_cycles_delta"
        ),
    )
    print(
        "Sem sinal:",
        performance.get(
            "no_signal_cycles_delta"
        ),
    )
    print(
        "Falhas:",
        performance.get(
            "failed_cycles_delta"
        ),
    )
    print(
        "Trades:",
        performance.get("trade_count_delta"),
    )
    print(
        "Equity inicial:",
        performance.get("start_equity"),
    )
    print(
        "Equity final:",
        performance.get("end_equity"),
    )
    print(
        "Variação da equity:",
        performance.get("equity_delta"),
    )
    print(
        "Retorno da sessão:",
        performance.get(
            "session_return_rate"
        ),
    )
    print(
        "Drawdown máximo:",
        performance.get(
            "max_drawdown_rate"
        ),
    )
    print(
        "Erros de endpoint:",
        summary.get("endpoint_errors"),
    )
    print(
        "Violações de segurança:",
        summary.get("safety_violations"),
    )

    return (
        0
        if summary.get("status") == "PASS"
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(main())
