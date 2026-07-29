from __future__ import annotations

import argparse

import httpx


BASE_PATH = (
    "/real-markets/economics"
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
        assert payload[field] is False

    assert (
        payload[
            "economic_analysis_only"
        ]
        is True
    )
    assert payload["shadow_only"] is True
    assert (
        payload[
            "order_submission_available"
        ]
        is False
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
    mock_market = None
    polymarket = None

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=90,
    ) as client:
        try:
            response = client.get(
                f"{BASE_PATH}/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload[
                    "manual_match_required"
                ]
                is True
            )

            print(
                "[PASS] Saúde do motor econômico"
            )
            print(
                "       Pares confirmados:",
                payload.get(
                    "confirmed_matches"
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
                f"{BASE_PATH}/configuration"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload[
                    "supported_structure"
                ]
                == "BINARY_YES_NO"
            )

            print(
                "[PASS] Configuração econômica"
            )
            print(
                "       Edge mínimo:",
                payload["configuration"].get(
                    "min_net_edge"
                ),
            )
            print(
                "       Idade máxima:",
                payload["configuration"].get(
                    "max_snapshot_age_seconds"
                ),
                "s",
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Configuração:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/real-markets/markets",
                params={
                    "connector_id": (
                        "mock-real-market"
                    ),
                    "limit": 2,
                },
            )
            response.raise_for_status()

            payload = response.json()
            assert payload["count"] >= 1

            mock_market = (
                payload["markets"][0]
            )

            print(
                "[PASS] Mercado mock localizado"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Mercado mock:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/real-markets/polymarket/markets",
                params={
                    "limit": 3,
                },
            )
            response.raise_for_status()

            payload = response.json()
            assert payload["count"] >= 1

            polymarket = (
                payload["markets"][0]
            )

            print(
                "[PASS] Mercado externo localizado"
            )
            print(
                "       Mercado:",
                polymarket.get("title"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Mercado externo:",
                exc,
            )
            failed += 1

        try:
            assert mock_market is not None
            assert polymarket is not None

            response = client.get(
                f"{BASE_PATH}/preview",
                params={
                    "left_connector_id": (
                        mock_market[
                            "connector_id"
                        ]
                    ),
                    "left_market_id": (
                        mock_market[
                            "market_id"
                        ]
                    ),
                    "right_connector_id": (
                        polymarket[
                            "connector_id"
                        ]
                    ),
                    "right_market_id": (
                        polymarket[
                            "market_id"
                        ]
                    ),
                    "force_refresh": "true",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload[
                    "manual_match_confirmed"
                ]
                is False
            )

            assert (
                payload["status"]
                in {
                    "PROFITABLE",
                    "NOT_PROFITABLE",
                    "REJECTED",
                }
            )

            print(
                "[PASS] Preview econômico"
            )
            print(
                "       Status:",
                payload.get("status"),
            )

            best = (
                payload.get(
                    "best_direction"
                )
                or {}
            )

            print(
                "       Lucro líquido simulado:",
                best.get(
                    "net_profit"
                ),
            )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Preview econômico:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/opportunities",
                params={
                    "force_refresh": "false",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["status"]
                in {
                    "NO_CONFIRMED_MATCHES",
                    "EVALUATED",
                }
            )

            print(
                "[PASS] Avaliação de pares confirmados"
            )
            print(
                "       Estado:",
                payload.get("status"),
            )
            print(
                "       Lucrativos:",
                payload.get(
                    "profitable"
                ),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Oportunidades:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/dashboard"
            )
            response.raise_for_status()

            assert (
                "Motor Econômico de Oportunidades"
                in response.text
            )
            assert (
                "Shadow mode"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-order-submission"
                )
                == "false"
            )
            assert (
                response.headers.get(
                    "x-predarb-live-authorization"
                )
                == "false"
            )

            print("[PASS] Dashboard")
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Dashboard:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/architecture"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["phase"] == "9D"
            assert (
                "order_creation"
                in payload[
                    "explicitly_excluded"
                ]
            )
            assert (
                "private_keys"
                in payload[
                    "explicitly_excluded"
                ]
            )

            print(
                "[PASS] Arquitetura e proteções"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Arquitetura:",
                exc,
            )
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
