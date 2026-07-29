from __future__ import annotations

import argparse
import json

import httpx


def ensure_safe(payload):
    for field in (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized",
    ):
        assert payload[field] is False

    assert payload["read_only"] is True


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
                "/paper/final-validation/evidence/health"
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            print("[PASS] Saúde do arquivo probatório")
            print("       Evidências:", payload.get("total_entries"))
            print("       Integridade:", payload.get("integrity_status"))
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/final-validation/evidence/capture",
                params={
                    "confirm":
                        "CAPTURE-FINAL-PAPER-VALIDATION-EVIDENCE",
                },
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            assert payload["status"] == "captured"
            assert payload["integrity"]["integrity_status"] == "VALID"

            print("[PASS] Captura de evidência")
            print("       Status:", payload["evidence"].get("status"))
            print("       Hash:", payload["evidence"].get("entry_hash"))
            passed += 1

        except Exception as exc:
            print("[FAIL] Captura:", exc)
            failed += 1

        for endpoint in (
            "/paper/final-validation/evidence/summary",
            "/paper/final-validation/evidence/verify",
            "/paper/final-validation/evidence/latest",
            "/paper/final-validation/evidence/entries?limit=25",
            "/paper/final-validation/evidence/snapshot?limit=25",
        ):
            try:
                response = client.get(endpoint)
                response.raise_for_status()
                payload = response.json()
                ensure_safe(payload)
                print(f"[PASS] {endpoint}")
                passed += 1

            except Exception as exc:
                print(f"[FAIL] {endpoint}: {exc}")
                failed += 1

        try:
            response = client.get(
                "/paper/final-validation/evidence/dashboard"
            )
            response.raise_for_status()

            assert (
                "Evidências da Validação Final Paper"
                in response.text
            )
            assert "Próxima fase não autorizada" in response.text
            assert (
                response.headers.get(
                    "x-predarb-next-step-authorization"
                )
                == "false"
            )

            print("[PASS] Dashboard")
            passed += 1

        except Exception as exc:
            print("[FAIL] Dashboard:", exc)
            failed += 1

        try:
            csv_response = client.get(
                "/paper/final-validation/evidence/export.csv"
            )
            csv_response.raise_for_status()

            json_response = client.get(
                "/paper/final-validation/evidence/export.json"
            )
            json_response.raise_for_status()

            payload = json.loads(json_response.text)
            ensure_safe(payload)

            assert "text/csv" in csv_response.headers.get(
                "content-type",
                "",
            )
            assert payload["integrity"]["integrity_status"] == "VALID"

            print("[PASS] Exportações CSV e JSON")
            passed += 1

        except Exception as exc:
            print("[FAIL] Exportações:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
