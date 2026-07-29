from __future__ import annotations

import argparse
import json

import httpx


BASE_PATH = (
    "/paper/final-assurance/"
    "qualification-certification"
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
                f"{BASE_PATH}/health"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["scope"]
                == (
                    "PAPER_QUALIFICATION_"
                    "CERTIFICATION_ONLY"
                )
            )

            print(
                "[PASS] Saúde da certificação"
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
                    "certification_score"
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
                f"{BASE_PATH}/report"
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
                "[PASS] Relatório consolidado"
            )

            print(
                "       Gate:",
                payload["summary"].get(
                    "gate_status"
                ),
            )

            print(
                "       Histórico:",
                payload["summary"].get(
                    "gate_history_entries"
                ),
            )

            print(
                "       Sequência:",
                payload["summary"].get(
                    "current_streak"
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
                f"{BASE_PATH}/dashboard"
            )

            response.raise_for_status()

            assert (
                "Certificação da Qualificação Final Paper"
                in response.text
            )

            assert (
                "Próxima fase não autorizada"
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
                f"{BASE_PATH}/export.json"
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
                == (
                    "PAPER_QUALIFICATION_"
                    "CERTIFICATION_ONLY"
                )
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
