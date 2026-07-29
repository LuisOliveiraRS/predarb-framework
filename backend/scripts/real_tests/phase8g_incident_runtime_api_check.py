from __future__ import annotations

import argparse
import time

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

    parser.add_argument(
        "--wait-seconds",
        type=float,
        default=6.5,
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
                "/paper/performance/incidents/runtime/health"
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
            assert (
                payload["manual_start_required"]
                is True
            )

            print("[PASS] Saúde do runtime")
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde do runtime:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/performance/incidents/runtime/cycle",
                params={
                    "confirm":
                        "CAPTURE-PAPER-INCIDENTS",
                },
            )
            response.raise_for_status()
            ensure_safe(response.json())

            print("[PASS] Ciclo manual")
            passed += 1

        except Exception as exc:
            print("[FAIL] Ciclo manual:", exc)
            failed += 1

        initial_cycles = 0

        try:
            response = client.get(
                "/paper/performance/incidents/runtime/status"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            initial_cycles = int(
                payload.get(
                    "total_cycles",
                    0,
                )
            )

            print("[PASS] Estado inicial")
            passed += 1

        except Exception as exc:
            print("[FAIL] Estado inicial:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/performance/incidents/runtime/start",
                params={
                    "confirm":
                        "START-PAPER-INCIDENT-RUNTIME",
                    "interval_seconds": 5,
                    "run_immediately": "false",
                },
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["running"] is True

            print("[PASS] Runtime iniciado")
            passed += 1

        except Exception as exc:
            print("[FAIL] Início do runtime:", exc)
            failed += 1

        time.sleep(
            max(5.5, args.wait_seconds)
        )

        try:
            response = client.get(
                "/paper/performance/incidents/runtime/status"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert int(
                payload.get(
                    "total_cycles",
                    0,
                )
            ) > initial_cycles

            print("[PASS] Captura periódica")
            print(
                "       Ciclos:",
                payload.get("total_cycles"),
            )
            print(
                "       Sucessos:",
                payload.get(
                    "successful_cycles"
                ),
            )
            print(
                "       Falhas:",
                payload.get("failed_cycles"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Captura periódica:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/performance/incidents/runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-INCIDENT-RUNTIME",
                },
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["running"] is False

            print("[PASS] Runtime encerrado")
            passed += 1

        except Exception as exc:
            print("[FAIL] Encerramento:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/performance/incidents/runtime/last-cycle"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["last_cycle_at"]

            print("[PASS] Último ciclo disponível")
            passed += 1

        except Exception as exc:
            print("[FAIL] Último ciclo:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
