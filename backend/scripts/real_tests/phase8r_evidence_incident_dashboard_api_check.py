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
    assert (
        payload["live_authorization"]
        is False
    )
    assert (
        payload["read_only"]
        is True
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
                "/paper/certification/evidence/incidents/ui/dashboard"
            )
            response.raise_for_status()

            assert (
                "Incidentes das Evidências"
                in response.text
            )
            assert (
                "Reconhecimento não resolve alerta"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
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
                "/paper/certification/evidence/incidents/ui/snapshot"
                "?limit=250"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print(
                "[PASS] Snapshot consolidado"
            )
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
            print(
                "       Monitor:",
                payload["monitor"].get(
                    "status"
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
            response = client.post(
                "/paper/certification/evidence/incidents/capture",
                params={
                    "confirm":
                        "CAPTURE-PAPER-EVIDENCE-INCIDENTS",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload[
                "status"
            ] == "captured"

            print(
                "[PASS] Captura administrativa"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/paper/certification/evidence/incidents/ui/snapshot"
                "?limit=250"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["summary"]["snapshots"]
                >= 1
            )

            print(
                "[PASS] Dashboard reflete captura"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Reflexo da captura:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/paper/certification/evidence/incidents/ui/export.csv"
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
                    "x-predarb-live-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Exportação CSV"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Exportação CSV:",
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
