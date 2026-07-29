from __future__ import annotations

import argparse
import time

import httpx


def ensure_safe(payload):
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False
    assert payload["live_authorization"] is False


def wait_for_cycle(
    client: httpx.Client,
    *,
    initial_cycles: int,
    timeout_seconds: float = 8.0,
):
    deadline = time.monotonic() + timeout_seconds

    while time.monotonic() < deadline:
        response = client.get(
            "/paper/certification/evidence/"
            "incident-runtime/status"
        )
        response.raise_for_status()

        payload = response.json()
        ensure_safe(payload)

        if int(
            payload.get("total_cycles", 0)
        ) > initial_cycles:
            return payload

        time.sleep(0.25)

    raise AssertionError(
        "O ciclo imediato não foi concluído no tempo esperado."
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
                "/paper/certification/evidence/"
                "incident-runtime/health"
            )
            response.raise_for_status()

            payload = response.json()

            assert payload["execution_authorized"] is False
            assert payload["live_execution"] is False
            assert payload["financial_execution"] is False
            assert payload["live_authorization"] is False
            assert payload["manual_start_required"] is True

            print("[PASS] Saúde do runtime")
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/certification/evidence/"
                "incident-runtime/cycle",
                params={
                    "confirm":
                        "CAPTURE-PAPER-EVIDENCE-INCIDENTS",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print("[PASS] Ciclo manual")
            print(
                "       Monitor:",
                payload.get("monitor_status"),
            )
            print(
                "       Criados:",
                payload.get("created"),
            )
            print(
                "       Resolvidos:",
                payload.get("resolved"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Ciclo manual:", exc)
            failed += 1

        initial_cycles = 0

        try:
            response = client.get(
                "/paper/certification/evidence/"
                "incident-runtime/status"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            initial_cycles = int(
                payload.get("total_cycles", 0)
            )

            print("[PASS] Estado inicial")
            passed += 1

        except Exception as exc:
            print("[FAIL] Estado inicial:", exc)
            failed += 1

        try:
            client.post(
                "/paper/certification/evidence/"
                "incident-runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-EVIDENCE-INCIDENT-RUNTIME",
                },
            )

            response = client.post(
                "/paper/certification/evidence/"
                "incident-runtime/start",
                params={
                    "confirm":
                        "START-PAPER-EVIDENCE-INCIDENT-RUNTIME",
                    "interval_seconds": 30,
                    "run_immediately": "true",
                },
            )

            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["running"] is True

            print("[PASS] Runtime iniciado")
            passed += 1

        except Exception as exc:
            print("[FAIL] Início:", exc)
            failed += 1

        try:
            payload = wait_for_cycle(
                client,
                initial_cycles=initial_cycles,
            )

            print("[PASS] Captura imediata")
            print(
                "       Ciclos:",
                payload.get("total_cycles"),
            )
            print(
                "       Sucessos:",
                payload.get("successful_cycles"),
            )
            print(
                "       Falhas:",
                payload.get("failed_cycles"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Captura imediata:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/certification/evidence/"
                "incident-runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-EVIDENCE-INCIDENT-RUNTIME",
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
                "/paper/certification/evidence/"
                "incident-runtime/last-cycle"
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
