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
        for label, endpoint in (
            (
                "Saúde do monitor",
                "/paper/final-validation/evidence/monitor/health",
            ),
            (
                "Alertas",
                "/paper/final-validation/evidence/monitor/alerts",
            ),
            (
                "Score",
                "/paper/final-validation/evidence/monitor/score",
            ),
            (
                "Snapshot",
                "/paper/final-validation/evidence/monitor/snapshot",
            ),
        ):
            try:
                response = client.get(endpoint)
                response.raise_for_status()

                payload = response.json()
                ensure_safe(payload)

                print(f"[PASS] {label}")

                if label == "Snapshot":
                    print(
                        "       Status:",
                        payload.get("status"),
                    )
                    print(
                        "       Score:",
                        payload.get("score"),
                    )
                    print(
                        "       Integridade:",
                        (
                            payload.get("summary")
                            or {}
                        ).get("integrity_status"),
                    )

                passed += 1

            except Exception as exc:
                print(f"[FAIL] {label}: {exc}")
                failed += 1

        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/monitor/dashboard"
            )
            response.raise_for_status()

            assert (
                "Monitor das Evidências Finais"
                in response.text
            )
            assert (
                "Somente leitura"
                in response.text
            )
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
            response = client.get(
                "/paper/final-validation/"
                "evidence/monitor/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            print("[PASS] Exportação JSON")
            passed += 1

        except Exception as exc:
            print("[FAIL] Exportação:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
