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
                "/paper/performance/dashboard"
            )
            response.raise_for_status()

            assert (
                "Desempenho Paper"
                in response.text
            )
            assert (
                "Painel somente leitura"
                in response.text
            )

            print(
                "[PASS] Dashboard HTML"
            )
            passed += 1

        except Exception as exc:
            print(
                f"[FAIL] Dashboard HTML: {exc}"
            )
            failed += 1

        try:
            response = client.get(
                "/paper/performance/snapshot",
                params={
                    "report_limit": 50,
                    "history_limit": 1000,
                },
            )
            response.raise_for_status()

            payload = response.json()

            assert (
                payload[
                    "execution_authorized"
                ]
                is False
            )
            assert (
                payload["live_execution"]
                is False
            )
            assert payload["read_only"] is True

            print(
                "[PASS] Snapshot consolidado"
            )
            print(
                "       Sessões:",
                payload["summary"].get(
                    "total_reports"
                ),
            )
            print(
                "       Pontos históricos:",
                len(payload.get("history", [])),
            )
            passed += 1

        except Exception as exc:
            print(
                f"[FAIL] Snapshot: {exc}"
            )
            failed += 1

        try:
            response = client.get(
                "/paper/performance/export.csv"
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
                    "x-predarb-live-execution"
                )
                == "false"
            )

            print(
                "[PASS] Exportação CSV"
            )
            passed += 1

        except Exception as exc:
            print(
                f"[FAIL] Exportação CSV: {exc}"
            )
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
