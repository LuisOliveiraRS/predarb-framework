from __future__ import annotations

import argparse
import json

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
        base_url=args.base_url.rstrip(
            "/"
        ),
        timeout=30,
    ) as client:
        try:
            response = client.get(
                "/paper/certification/"
                "assurance/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["scope"]
                == "PAPER_ONLY"
            )

            print(
                "[PASS] Saúde do centro"
            )
            print(
                "       Status:",
                payload.get("status"),
            )
            print(
                "       Score:",
                payload.get(
                    "assurance_score"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Saúde:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/paper/certification/"
                "assurance/snapshot"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["scope"]
                == "PAPER_ONLY"
            )

            print(
                "[PASS] Snapshot consolidado"
            )
            print(
                "       Certificação:",
                payload["summary"].get(
                    "certification_status"
                ),
            )
            print(
                "       Monitor:",
                payload["summary"].get(
                    "monitor_status"
                ),
            )
            print(
                "       Cadeia:",
                payload["summary"].get(
                    "chain_status"
                ),
            )
            print(
                "       Incidentes ativos:",
                payload["summary"].get(
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
            response = client.get(
                "/paper/certification/"
                "assurance/dashboard"
            )
            response.raise_for_status()

            assert (
                "Centro de Garantia Paper"
                in response.text
            )
            assert (
                "Não autoriza execução live"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Dashboard"
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
                "/paper/certification/"
                "assurance/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            assert (
                payload["scope"]
                == "PAPER_ONLY"
            )

            print(
                "[PASS] Exportação JSON"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Exportação:",
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
