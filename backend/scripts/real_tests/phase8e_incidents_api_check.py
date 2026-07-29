from __future__ import annotations

import argparse

import httpx


def ensure_safe(payload):
    assert (
        payload["execution_authorized"]
        is False
    )
    assert payload["live_execution"] is False
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
                "/paper/performance/incidents/health"
            )
            response.raise_for_status()
            ensure_safe(response.json())
            print("[PASS] Saúde do journal")
            passed += 1
        except Exception as exc:
            print("[FAIL] Saúde do journal:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/performance/incidents/capture",
                params={
                    "confirm":
                        "CAPTURE-PAPER-INCIDENTS",
                },
            )
            response.raise_for_status()
            payload = response.json()
            ensure_safe(payload)

            print("[PASS] Captura confirmada")
            print(
                "       Criados:",
                len(payload.get("created", [])),
            )
            print(
                "       Resolvidos:",
                len(payload.get("resolved", [])),
            )
            passed += 1
        except Exception as exc:
            print("[FAIL] Captura:", exc)
            failed += 1

        for endpoint in (
            "/paper/performance/incidents/summary",
            "/paper/performance/incidents/active",
            "/paper/performance/incidents/history",
            "/paper/performance/incidents/snapshots",
        ):
            try:
                response = client.get(endpoint)
                response.raise_for_status()
                ensure_safe(response.json())
                print(f"[PASS] {endpoint}")
                passed += 1
            except Exception as exc:
                print(f"[FAIL] {endpoint}: {exc}")
                failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
