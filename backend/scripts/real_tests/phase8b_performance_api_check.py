from __future__ import annotations

import argparse
import json
from typing import Any

import httpx


def ensure_safe(
    payload: Any,
    *,
    path: str = "root",
) -> list[str]:
    violations: list[str] = []

    if isinstance(payload, dict):
        for key, value in payload.items():
            current = f"{path}.{key}"

            if key in {
                "execution_authorized",
                "live_execution",
            } and value is True:
                violations.append(
                    f"{current}=true"
                )

            violations.extend(
                ensure_safe(
                    value,
                    path=current,
                )
            )

    elif isinstance(payload, list):
        for index, item in enumerate(payload):
            violations.extend(
                ensure_safe(
                    item,
                    path=f"{path}[{index}]",
                )
            )

    return violations


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    args = parser.parse_args()

    endpoints = (
        "/paper/performance/health",
        "/paper/performance/summary",
        "/paper/performance/reports?limit=10",
        "/paper/performance/history?limit=25",
    )

    passed = 0
    failed = 0
    results: dict[str, Any] = {}

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=30,
    ) as client:
        for endpoint in endpoints:
            try:
                response = client.get(
                    endpoint
                )
                response.raise_for_status()
                payload = response.json()

                violations = ensure_safe(
                    payload,
                    path=endpoint,
                )

                if violations:
                    raise AssertionError(
                        violations
                    )

                results[endpoint] = payload
                passed += 1

                print(
                    f"[PASS] {endpoint}"
                )

            except Exception as exc:
                failed += 1
                print(
                    f"[FAIL] {endpoint}: {exc}"
                )

    summary = results.get(
        "/paper/performance/summary",
        {},
    )

    print()
    print(
        "Relatórios encontrados:",
        summary.get("total_reports"),
    )
    print(
        "Ciclos consolidados:",
        summary.get("total_cycles"),
    )
    print(
        "Trades consolidados:",
        summary.get("total_trades"),
    )
    print(
        "Variação acumulada da equity:",
        summary.get(
            "cumulative_equity_delta"
        ),
    )
    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
