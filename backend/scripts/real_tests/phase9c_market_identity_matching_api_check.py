from __future__ import annotations

import argparse

import httpx


BASE_PATH = (
    "/real-markets/matching"
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

    assert payload["market_data_only"] is True

    if (
        "automatic_matching_authorized"
        in payload
    ):
        assert (
            payload[
                "automatic_matching_authorized"
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
                    "manual_confirmation_required"
                ]
                is True
            )

            print("[PASS] Saúde do matching")
            print(
                "       Limiar candidato:",
                payload.get(
                    "candidate_threshold"
                ),
            )
            print(
                "       Limiar forte:",
                payload.get(
                    "strong_threshold"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde:", exc)
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/identities",
                params={
                    "connector_id": (
                        "mock-real-market"
                    ),
                    "limit": 10,
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1
            mock_market = (
                payload["identities"][0]
            )

            assert (
                len(
                    mock_market[
                        "fingerprint"
                    ]
                )
                == 64
            )

            print(
                "[PASS] Identidades do mock"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Identidades mock:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/identities",
                params={
                    "connector_id": (
                        "polymarket"
                    ),
                    "limit": 5,
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1
            polymarket = (
                payload["identities"][0]
            )

            assert (
                polymarket[
                    "connector_id"
                ]
                == "polymarket"
            )

            print(
                "[PASS] Identidades externas"
            )
            print(
                "       Primeiro mercado:",
                polymarket.get("title"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Identidades externas:",
                exc,
            )
            failed += 1

        try:
            assert mock_market is not None
            assert polymarket is not None

            response = client.get(
                f"{BASE_PATH}/compare",
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
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            comparison = (
                payload["comparison"]
            )

            assert (
                comparison["status"]
                in {
                    "STRONG_CANDIDATE",
                    "CANDIDATE",
                    "REJECTED",
                }
            )

            print(
                "[PASS] Comparação individual"
            )
            print(
                "       Status:",
                comparison.get("status"),
            )
            print(
                "       Score:",
                comparison.get("score"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Comparação:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/candidates",
                params={
                    "connector_a": (
                        "mock-real-market"
                    ),
                    "connector_b": (
                        "polymarket"
                    ),
                    "limit_per_connector": 3,
                    "include_rejected": "true",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["compared_pairs"]
                >= 1
            )
            assert (
                payload["count"]
                == payload[
                    "compared_pairs"
                ]
            )

            print(
                "[PASS] Geração de candidatos"
            )
            print(
                "       Pares comparados:",
                payload.get(
                    "compared_pairs"
                ),
            )
            print(
                "       Candidatos retornados:",
                payload.get("count"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Candidatos:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/manual-matches"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert "matches" in payload

            print(
                "[PASS] Correspondências manuais"
            )
            print(
                "       Confirmadas:",
                payload.get("count"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Correspondências:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/dashboard"
            )
            response.raise_for_status()

            assert (
                "Identidade e Correspondência de Mercados"
                in response.text
            )
            assert (
                "CONFIRM-REAL-MARKET-MATCH"
                in response.text
            )
            assert (
                "REMOVE-REAL-MARKET-MATCH"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-automatic-matching"
                )
                == "false"
            )

            print("[PASS] Dashboard")
            passed += 1

        except Exception as exc:
            print("[FAIL] Dashboard:", exc)
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/architecture"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["phase"] == "9C"
            assert (
                payload[
                    "manual_confirmation_required"
                ]
                is True
            )
            assert (
                "automatic_pair_activation"
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
