from __future__ import annotations

import argparse

import httpx


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
                "/paper/final-validation/"
                "evidence/incidents/ui/dashboard"
            )

            response.raise_for_status()

            assert (
                "Incidentes das Evidências Finais"
                in response.text
            )

            assert (
                "Captura manual confirmada"
                in response.text
            )

            assert (
                response.headers.get(
                    "x-predarb-next-step-authorization"
                )
                == "false"
            )

            print(
                "[PASS] Dashboard HTML"
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
                "/paper/final-validation/"
                "evidence/incidents/ui/snapshot"
            )

            response.raise_for_status()

            payload = response.json()
            ensure_safe(
                payload
            )

            print(
                "[PASS] Snapshot consolidado"
            )

            print(
                "       Monitor:",
                (
                    payload.get("monitor")
                    or {}
                ).get("status"),
            )

            print(
                "       Ativos:",
                (
                    payload.get("summary")
                    or {}
                ).get(
                    "active_incidents"
                ),
            )

            print(
                "       Resolvidos:",
                (
                    payload.get("summary")
                    or {}
                ).get(
                    "resolved_incidents"
                ),
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Snapshot:",
                exc,
            )

            failed += 1

        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/incidents/ui/export.csv"
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
                "[FAIL] Exportação:",
                exc,
            )

            failed += 1

        try:
            response = client.post(
                "/paper/final-validation/"
                "evidence/incidents/capture",
                params={
                    "confirm":
                        "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS",
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
                "[PASS] Captura administrativa"
            )

            print(
                "       Criados:",
                len(
                    payload.get(
                        "created"
                    )
                    or []
                ),
            )

            print(
                "       Resolvidos:",
                len(
                    payload.get(
                        "resolved"
                    )
                    or []
                ),
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Captura:",
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
