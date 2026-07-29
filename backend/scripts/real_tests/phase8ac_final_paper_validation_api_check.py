from __future__ import annotations

import argparse
import json

import httpx


def ensure_safe(
    payload,
):
    assert (
        payload[
            "paper_execution_authorized"
        ]
        is False
    )
    assert (
        payload[
            "execution_authorized"
        ]
        is False
    )
    assert (
        payload[
            "live_execution"
        ]
        is False
    )
    assert (
        payload[
            "financial_execution"
        ]
        is False
    )
    assert (
        payload[
            "live_authorization"
        ]
        is False
    )
    assert (
        payload["read_only"]
        is True
    )
    assert (
        payload[
            "next_step_authorized"
        ]
        is False
    )


def main() -> int:
    parser = (
        argparse.ArgumentParser()
    )

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
                "/paper/final-validation/health"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["scope"]
                == "PAPER_VALIDATION_ONLY"
            )

            print(
                "[PASS] Saúde da validação final"
            )

            print(
                "       Status:",
                payload.get(
                    "status"
                ),
            )

            print(
                "       Score:",
                payload.get(
                    "validation_score"
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
                "/paper/final-validation/report"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                "checks"
                in payload
            )

            assert (
                "components"
                in payload
            )

            print(
                "[PASS] Relatório final"
            )

            print(
                "       Garantia:",
                payload["summary"].get(
                    "assurance_status"
                ),
            )

            print(
                "       Gate:",
                payload["summary"].get(
                    "gate_status"
                ),
            )

            print(
                "       Sequência QUALIFIED:",
                payload["summary"].get(
                    "qualified_streak"
                ),
            )

            print(
                "       Falhas de runtime:",
                payload["summary"].get(
                    "total_runtime_failures"
                ),
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Relatório:",
                exc,
            )

            failed += 1

        try:
            response = client.get(
                "/paper/final-validation/dashboard"
            )

            response.raise_for_status()

            assert (
                "Validação Final Paper"
                in response.text
            )

            assert (
                "Não autoriza a próxima fase"
                in response.text
            )

            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
                )
                == "false"
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
                "/paper/final-validation/export.json"
            )

            response.raise_for_status()

            payload = json.loads(
                response.text
            )

            ensure_safe(
                payload
            )

            assert (
                payload["scope"]
                == "PAPER_VALIDATION_ONLY"
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
