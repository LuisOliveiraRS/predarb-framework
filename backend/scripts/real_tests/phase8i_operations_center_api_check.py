from __future__ import annotations

import argparse
import json

import httpx


def ensure_safe(payload):
    assert (
        payload["execution_authorized"]
        is False
    )
    assert payload["live_execution"] is False
    assert (
        payload["financial_execution"]
        is False
    )


def main() -> int:
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--base-url",
        default="http://127.0.0.1:8000",
    )

    args = parser.parse_args()

    passed = 0
    failed = 0

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=30,
    ) as client:
        try:
            response = client.get(
                "/paper/operations/health"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["read_only"] is True
            assert (
                payload["manual_start_required"]
                is True
            )

            print("[PASS] Saúde consolidada")
            print(
                "       Status:",
                payload.get("status"),
            )
            print(
                "       Score:",
                payload.get("monitor_score"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde consolidada:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/operations/snapshot"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["read_only"] is True
            assert "performance" in payload
            assert "monitor" in payload
            assert "incidents" in payload
            assert "runtime" in payload

            print("[PASS] Snapshot unificado")
            print(
                "       Relatórios:",
                payload["diagnostics"].get(
                    "reports"
                ),
            )
            print(
                "       Ciclos:",
                payload["diagnostics"].get(
                    "cycles"
                ),
            )
            print(
                "       Incidentes ativos:",
                payload["diagnostics"].get(
                    "active_incidents"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Snapshot unificado:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/operations/dashboard"
            )
            response.raise_for_status()

            assert (
                "Centro de Operações Paper"
                in response.text
            )
            assert (
                "Centro somente leitura"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-financial-execution"
                )
                == "false"
            )

            print("[PASS] Dashboard operacional")
            passed += 1

        except Exception as exc:
            print("[FAIL] Dashboard:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/operations/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            assert (
                "application/json"
                in response.headers.get(
                    "content-type",
                    "",
                )
            )
            assert (
                response.headers.get(
                    "x-predarb-financial-execution"
                )
                == "false"
            )

            print("[PASS] Exportação JSON")
            passed += 1

        except Exception as exc:
            print("[FAIL] Exportação JSON:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
