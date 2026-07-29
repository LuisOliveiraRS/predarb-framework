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
                "/paper/certification/evidence/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["read_only"] is True

            print(
                "[PASS] Saúde do arquivo"
            )
            print(
                "       Cadeia:",
                payload.get(
                    "chain_status"
                ),
            )
            print(
                "       Evidências:",
                payload.get(
                    "total_entries"
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
            response = client.post(
                "/paper/certification/evidence/capture",
                params={
                    "confirm":
                        "CAPTURE-PAPER-CERTIFICATION-EVIDENCE",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["status"] == "captured"
            assert payload[
                "verification"
            ]["valid"] is True

            print(
                "[PASS] Captura encadeada"
            )
            print(
                "       Status:",
                payload["evidence"].get(
                    "status"
                ),
            )
            print(
                "       Hash:",
                payload["evidence"].get(
                    "evidence_hash"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura:",
                exc,
            )
            failed += 1

        for endpoint in (
            "/paper/certification/evidence/summary",
            "/paper/certification/evidence/verify",
            "/paper/certification/evidence/latest",
            "/paper/certification/evidence/entries?limit=25",
            "/paper/certification/evidence/snapshot?limit=25",
        ):
            try:
                response = client.get(
                    endpoint
                )
                response.raise_for_status()

                payload = response.json()
                ensure_safe(payload)

                print(
                    f"[PASS] {endpoint}"
                )
                passed += 1

            except Exception as exc:
                print(
                    f"[FAIL] {endpoint}: {exc}"
                )
                failed += 1

        try:
            response = client.get(
                "/paper/certification/evidence/dashboard"
            )
            response.raise_for_status()

            assert (
                "Evidências da Certificação"
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
                "/paper/certification/evidence/export.csv"
            )
            response.raise_for_status()

            assert (
                "text/csv"
                in response.headers.get(
                    "content-type",
                    "",
                )
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

        try:
            response = client.get(
                "/paper/certification/evidence/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            assert payload[
                "verification"
            ]["valid"] is True

            print(
                "[PASS] Exportação JSON"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Exportação JSON:",
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
