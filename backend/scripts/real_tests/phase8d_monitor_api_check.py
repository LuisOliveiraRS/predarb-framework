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
        for endpoint in (
            "/paper/performance/monitor/health",
            "/paper/performance/monitor/alerts",
            "/paper/performance/monitor/score",
            "/paper/performance/monitor/snapshot",
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

                if endpoint.endswith(
                    "/snapshot"
                ):
                    print(
                        "       Status:",
                        payload.get("status"),
                    )
                    print(
                        "       Score:",
                        payload.get("score"),
                    )
                    print(
                        "       Alertas:",
                        len(
                            payload.get(
                                "alerts",
                                [],
                            )
                        ),
                    )

                passed += 1

            except Exception as exc:
                print(
                    f"[FAIL] {endpoint}: {exc}"
                )
                failed += 1

        try:
            response = client.get(
                "/paper/performance/monitor/dashboard"
            )
            response.raise_for_status()

            assert "Monitor Paper" in response.text
            assert (
                response.headers.get(
                    "x-predarb-live-execution"
                )
                == "false"
            )

            print(
                "[PASS] Dashboard do monitor"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Dashboard do monitor:",
                exc,
            )
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
