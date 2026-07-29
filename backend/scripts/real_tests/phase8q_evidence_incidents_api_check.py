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
                "/paper/certification/evidence/incidents/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print(
                "[PASS] Saúde do journal"
            )
            print(
                "       Ativos:",
                payload.get(
                    "active_incidents"
                ),
            )
            print(
                "       Total:",
                payload.get(
                    "total_incidents"
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
                "[PASS] Captura do monitor"
            )
            print(
                "       Criados:",
                len(
                    payload.get(
                        "created",
                        [],
                    )
                ),
            )
            print(
                "       Resolvidos:",
                len(
                    payload.get(
                        "resolved",
                        [],
                    )
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
            "/paper/certification/evidence/incidents/summary",
            "/paper/certification/evidence/incidents/active?limit=25",
            "/paper/certification/evidence/incidents/history?limit=25",
            "/paper/certification/evidence/incidents/snapshots?limit=25",
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
