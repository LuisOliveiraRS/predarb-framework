from __future__ import annotations

import argparse

import httpx


def ensure_safe(
    payload,
):
    for field in (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized",
    ):
        assert (
            payload[field]
            is False
        )


def main() -> int:
    parser = (
        argparse.ArgumentParser()
    )

    parser.add_argument(
        "--base-url",
        default=(
            "http://127.0.0.1:8000"
        ),
    )

    args = parser.parse_args()

    passed = 0
    failed = 0

    with httpx.Client(
        base_url=args.base_url.rstrip(
            "/"
        ),
        timeout=30,
    ) as client:
        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/incident-runtime/dashboard"
            )

            response.raise_for_status()

            assert (
                "Runtime dos Incidentes Finais"
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

            assert (
                response.headers.get(
                    "x-predarb-next-step-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Dashboard HTML"
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Dashboard:",
                exc,
            )

            failed += 1

        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/incident-runtime/snapshot"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["manual_start_required"]
                is True
            )

            print(
                "[PASS] Snapshot consolidado"
            )

            print(
                "       Runtime:",
                (
                    payload.get("runtime")
                    or {}
                ).get("status"),
            )

            print(
                "       Monitor:",
                (
                    payload.get("monitor")
                    or {}
                ).get("status"),
            )

            print(
                "       Incidentes ativos:",
                (
                    payload.get("journal")
                    or {}
                ).get(
                    "active_incidents"
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
                "/paper/final-validation/"
                "evidence/incident-runtime/stop",
                params={
                    "confirm":
                        "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
                },
            )

            response = client.post(
                "/paper/final-validation/"
                "evidence/incident-runtime/start",
                params={
                    "confirm":
                        "START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
                    "interval_seconds": 300,
                    "run_immediately": "false",
                },
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["running"]
                is True
            )

            print(
                "[PASS] Controle de início"
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Início:",
                exc,
            )

            failed += 1

        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/incident-runtime/snapshot"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

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
                "/paper/final-validation/"
                "evidence/incident-runtime/stop",
                params={
                    "confirm":
                        "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME",
                },
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["running"]
                is False
            )

            print(
                "[PASS] Controle de parada"
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Parada:",
                exc,
            )

            failed += 1

        try:
            response = client.post(
                "/paper/final-validation/"
                "evidence/incident-runtime/cycle",
                params={
                    "confirm":
                        "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS",
                },
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["status"]
                == "SUCCESS"
            )

            print(
                "[PASS] Captura manual"
            )

            print(
                "       Monitor:",
                payload.get(
                    "monitor_status"
                ),
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura manual:",
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
