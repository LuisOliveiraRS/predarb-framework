from __future__ import annotations

import argparse
import json

import httpx


BASE_PATH = (
    "/paper/final-assurance/"
    "qualification-certification/history"
)


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

    assert (
        payload["read_only"]
        is True
    )


def main() -> int:
    parser = argparse.ArgumentParser()

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
                f"{BASE_PATH}/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print(
                "[PASS] Saúde do histórico"
            )
            print(
                "       Registros:",
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
                f"{BASE_PATH}/capture",
                params={
                    "confirm": (
                        "CAPTURE-FINAL-PAPER-"
                        "QUALIFICATION-CERTIFICATION"
                    ),
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["status"]
                == "captured"
            )

            print(
                "[PASS] Captura da certificação"
            )
            print(
                "       Status:",
                (
                    payload.get("entry")
                    or {}
                ).get("status"),
            )
            print(
                "       Score:",
                (
                    payload.get("entry")
                    or {}
                ).get(
                    "certification_score"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura:",
                exc,
            )
            failed += 1

        for label, endpoint in (
            (
                "Resumo",
                f"{BASE_PATH}/summary",
            ),
            (
                "Último registro",
                f"{BASE_PATH}/latest",
            ),
            (
                "Entradas",
                f"{BASE_PATH}/entries?limit=50",
            ),
            (
                "Snapshot",
                f"{BASE_PATH}/snapshot?limit=50",
            ),
        ):
            try:
                response = client.get(
                    endpoint
                )
                response.raise_for_status()

                payload = response.json()
                ensure_safe(payload)

                print(
                    f"[PASS] {label}"
                )
                passed += 1

            except Exception as exc:
                print(
                    f"[FAIL] {label}:",
                    exc,
                )
                failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/dashboard"
            )
            response.raise_for_status()

            assert (
                "Histórico da Certificação Final Paper"
                in response.text
            )
            assert (
                "CAPTURE-FINAL-PAPER-QUALIFICATION-CERTIFICATION"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-next-step-authorization"
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
                f"{BASE_PATH}/export.csv"
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
                    "x-predarb-next-step-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Exportação CSV"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] CSV:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/export.json"
            )
            response.raise_for_status()

            payload = json.loads(
                response.text
            )
            ensure_safe(payload)

            print(
                "[PASS] Exportação JSON"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] JSON:",
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
