from __future__ import annotations

import argparse

import httpx


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
                "/paper/performance/incidents/dashboard"
            )
            response.raise_for_status()

            assert "Incidentes Paper" in response.text
            assert (
                response.headers.get(
                    "x-predarb-financial-execution"
                )
                == "false"
            )

            print("[PASS] Dashboard HTML")
            passed += 1

        except Exception as exc:
            print("[FAIL] Dashboard HTML:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/performance/incidents/snapshot",
                params={
                    "active_limit": 100,
                    "history_limit": 250,
                },
            )
            response.raise_for_status()
            payload = response.json()

            assert (
                payload["execution_authorized"]
                is False
            )
            assert payload["live_execution"] is False
            assert (
                payload["financial_execution"]
                is False
            )

            print("[PASS] Snapshot do dashboard")
            print(
                "       Ativos:",
                payload["summary"].get(
                    "active_incidents"
                ),
            )
            print(
                "       Resolvidos:",
                payload["summary"].get(
                    "resolved_incidents"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Snapshot:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/performance/incidents/export.csv"
            )
            response.raise_for_status()

            assert (
                "text/csv"
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

            print("[PASS] Exportação CSV")
            passed += 1

        except Exception as exc:
            print("[FAIL] Exportação CSV:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/performance/incidents/capture",
                params={
                    "confirm":
                        "CAPTURE-PAPER-INCIDENTS",
                },
            )
            response.raise_for_status()

            payload = response.json()

            assert (
                payload["execution_authorized"]
                is False
            )
            assert payload["live_execution"] is False

            print(
                "[PASS] Captura administrativa"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura administrativa:",
                exc,
            )
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
