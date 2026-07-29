from __future__ import annotations

import argparse

import httpx


def ensure_safe(payload):
    assert payload["paper_execution_authorized"] is False
    assert payload["execution_authorized"] is False
    assert payload["live_execution"] is False
    assert payload["financial_execution"] is False
    assert payload["live_authorization"] is False


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
                "/paper/certification/assurance/"
                "history-runtime/dashboard"
            )
            response.raise_for_status()

            assert (
                "Runtime do Histórico da Garantia"
                in response.text
            )
            assert (
                "Início manual obrigatório"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
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
                "/paper/certification/assurance/"
                "history-runtime/snapshot"
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
                "       Garantia:",
                payload["assurance"].get("status"),
            )
            print(
                "       Histórico:",
                payload["history"].get(
                    "total_entries"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Snapshot:", exc)
            failed += 1

        try:
            client.post(
                "/paper/certification/assurance/"
                "history-runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-ASSURANCE-HISTORY-RUNTIME",
                },
            )

            response = client.post(
                "/paper/certification/assurance/"
                "history-runtime/start",
                params={
                    "confirm":
                        "START-PAPER-ASSURANCE-HISTORY-RUNTIME",
                    "interval_seconds": 300,
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
                "/paper/certification/assurance/"
                "history-runtime/snapshot"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["runtime"]["running"] is True

            print(
                "[PASS] Dashboard reflete runtime ativo"
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Runtime ativo:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/certification/assurance/"
                "history-runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-ASSURANCE-HISTORY-RUNTIME",
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
                "/paper/certification/assurance/"
                "history-runtime/cycle",
                params={
                    "confirm":
                        "CAPTURE-PAPER-CERTIFICATION-ASSURANCE",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["status"] == "SUCCESS"

            print(
                "[PASS] Captura manual pelo painel"
            )
            print(
                "       Status:",
                payload.get("assurance_status"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Captura manual:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
