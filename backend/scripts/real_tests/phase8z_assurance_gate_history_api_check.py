from __future__ import annotations

import argparse

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
                "/paper/certification/"
                "assurance/gate/history/health"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            print(
                "[PASS] Saúde do histórico"
            )

            print(
                "       Avaliações:",
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
                "/paper/certification/"
                "assurance/gate/history/capture",
                params={
                    "confirm":
                        "CAPTURE-PAPER-ASSURANCE-QUALIFICATION",
                },
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            assert (
                payload["status"]
                == "captured"
            )

            print(
                "[PASS] Captura da avaliação"
            )

            print(
                "       Status:",
                payload["entry"].get(
                    "status"
                ),
            )

            print(
                "       Score:",
                payload["entry"].get(
                    "qualification_score"
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
            "/paper/certification/assurance/gate/history/summary",
            "/paper/certification/assurance/gate/history/latest",
            "/paper/certification/assurance/gate/history/entries?limit=25",
            "/paper/certification/assurance/gate/history/snapshot?limit=25",
        ):
            try:
                response = client.get(
                    endpoint
                )

                response.raise_for_status()

                payload = response.json()
                ensure_safe(
                    payload
                )

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
                "/paper/certification/"
                "assurance/gate/history/dashboard"
            )

            response.raise_for_status()

            assert (
                "Histórico do Gate de Qualificação"
                in response.text
            )

            assert (
                "Não autoriza execução live"
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
                "/paper/certification/"
                "assurance/gate/history/export.csv"
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
                    "x-predarb-live-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Exportação CSV"
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
