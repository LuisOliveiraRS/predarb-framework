from __future__ import annotations

import argparse

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
                "/paper/performance/incidents/runtime/dashboard"
            )
            response.raise_for_status()

            assert (
                "Controle do Runtime"
                in response.text
            )
            assert (
                "Início manual obrigatório"
                in response.text
            )
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
                "/paper/performance/incidents/runtime/snapshot"
            )
            response.raise_for_status()
            payload = response.json()

            ensure_safe(payload)

            assert (
                payload["manual_start_required"]
                is True
            )

            print("[PASS] Snapshot consolidado")
            print(
                "       Runtime:",
                payload["runtime"].get("status"),
            )
            print(
                "       Ciclos:",
                payload["runtime"].get(
                    "total_cycles"
                ),
            )
            print(
                "       Incidentes ativos:",
                payload["incidents"].get(
                    "active_incidents"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Snapshot:", exc)
            failed += 1

        try:
            client.post(
                "/paper/performance/incidents/runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-INCIDENT-RUNTIME",
                },
            )

            response = client.post(
                "/paper/performance/incidents/runtime/start",
                params={
                    "confirm":
                        "START-PAPER-INCIDENT-RUNTIME",
                    "interval_seconds": 60,
                    "run_immediately": "false",
                },
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["running"] is True

            print("[PASS] Controle de início")
            passed += 1

        except Exception as exc:
            print("[FAIL] Controle de início:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/performance/incidents/runtime/snapshot"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["runtime"]["running"]
                is True
            )

            print(
                "[PASS] Dashboard reflete runtime ativo"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Runtime ativo no dashboard:",
                exc,
            )
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

            print("[PASS] Controle de parada")
            passed += 1

        except Exception as exc:
            print("[FAIL] Controle de parada:", exc)
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
            payload = response.json()
            ensure_safe(payload)

            print("[PASS] Ciclo manual pelo controle")
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Ciclo manual pelo controle:",
                exc,
            )
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
