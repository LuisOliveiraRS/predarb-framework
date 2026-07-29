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
        base_url=args.base_url.rstrip("/"),
        timeout=30,
    ) as client:
        for endpoint in (
            "/paper/certification/evidence/monitor/health",
            "/paper/certification/evidence/monitor/alerts",
            "/paper/certification/evidence/monitor/score",
            "/paper/certification/evidence/monitor/snapshot",
        ):
            try:
                response = client.get(endpoint)
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
                        "       Cadeia:",
                        payload.get(
                            "diagnostics",
                            {},
                        ).get("chain_status"),
                    )
                    print(
                        "       Evidências:",
                        payload.get(
                            "diagnostics",
                            {},
                        ).get("total_entries"),
                    )

                passed += 1

            except Exception as exc:
                print(
                    f"[FAIL] {endpoint}: {exc}"
                )
                failed += 1

        try:
            response = client.get(
                "/paper/certification/evidence/monitor/dashboard"
            )
            response.raise_for_status()

            assert (
                "Monitor de Evidências"
                in response.text
            )
            assert (
                "Nenhuma evidência é criada"
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
                "/paper/certification/evidence/monitor/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
                )
                == "false"
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
