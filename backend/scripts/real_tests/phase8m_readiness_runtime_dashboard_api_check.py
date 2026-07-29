from __future__ import annotations

import argparse

import httpx


def ensure_safe(
    payload,
):
    assert (
        payload["execution_authorized"]
        is False
    )
    assert (
        payload["live_execution"]
        is False
    )
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
                "/paper/readiness/runtime/dashboard"
            )
            response.raise_for_status()

            assert (
                "Runtime de Readiness"
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

            print(
                "[PASS] Dashboard HTML"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Dashboard HTML:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/paper/readiness/runtime/snapshot"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["manual_start_required"]
                is True
            )

            print(
                "[PASS] Snapshot consolidado"
            )
            print(
                "       Runtime:",
                payload["runtime"].get(
                    "status"
                ),
            )
            print(
                "       Gate:",
                payload["gate"].get(
                    "status"
                ),
            )
            print(
                "       Histórico:",
                payload["history"].get(
                    "total_entries"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Snapshot:",
                exc,
            )
            failed += 1

        try:
            client.post(
                "/paper/readiness/runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-READINESS-RUNTIME",
                },
            )

            response = client.post(
                "/paper/readiness/runtime/start",
                params={
                    "confirm":
                        "START-PAPER-READINESS-RUNTIME",
                    "interval_seconds": 300,
                    "run_immediately": "false",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload[
                "running"
            ] is True

            print(
                "[PASS] Controle de início"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Controle de início:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/paper/readiness/runtime/snapshot"
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
                "[FAIL] Runtime ativo:",
                exc,
            )
            failed += 1

        try:
            response = client.post(
                "/paper/readiness/runtime/stop",
                params={
                    "confirm":
                        "STOP-PAPER-READINESS-RUNTIME",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload[
                "running"
            ] is False

            print(
                "[PASS] Controle de parada"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Controle de parada:",
                exc,
            )
            failed += 1

        try:
            response = client.post(
                "/paper/readiness/runtime/cycle",
                params={
                    "confirm":
                        "CAPTURE-PAPER-READINESS",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print(
                "[PASS] Avaliação manual pelo painel"
            )
            print(
                "       Status:",
                payload.get(
                    "readiness_status"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Avaliação manual:",
                exc,
            )
            failed += 1

    print()
    print(
        "Aprovados:",
        passed,
    )
    print(
        "Falhas:",
        failed,
    )

    return (
        0
        if failed == 0
        else 1
    )


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
