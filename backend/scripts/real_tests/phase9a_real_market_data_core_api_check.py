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
        assert payload[field] is False

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True


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
                "/real-markets/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload[
                    "manual_refresh_required"
                ]
                is True
            )

            print("[PASS] Saúde do núcleo")
            print(
                "       Estado:",
                payload.get("status"),
            )
            print(
                "       Conectores:",
                payload.get(
                    "registered_connectors"
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde:", exc)
            failed += 1

        try:
            response = client.get(
                "/real-markets/connectors"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1
            assert all(
                item.get("read_only") is True
                for item in payload[
                    "connectors"
                ]
            )

            print("[PASS] Registro de conectores")
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Conectores:",
                exc,
            )
            failed += 1

        market = None

        try:
            response = client.get(
                "/real-markets/markets",
                params={
                    "limit": 100,
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1

            market = payload["markets"][0]

            print("[PASS] Mercados normalizados")
            print(
                "       Primeiro mercado:",
                market.get("key"),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Mercados:", exc)
            failed += 1

        try:
            assert market is not None

            response = client.get(
                (
                    "/real-markets/markets/"
                    f"{market['connector_id']}/"
                    f"{market['market_id']}"
                ),
                params={
                    "force_refresh": "true",
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["snapshot"][
                    "market"
                ]["market_id"]
                == market["market_id"]
            )

            assert (
                len(
                    payload["snapshot"][
                        "quotes"
                    ]
                )
                >= 2
            )

            print("[PASS] Snapshot individual")
            passed += 1

        except Exception as exc:
            print("[FAIL] Snapshot:", exc)
            failed += 1

        try:
            response = client.post(
                "/real-markets/refresh",
                params={
                    "confirm": (
                        "REFRESH-REAL-MARKET-DATA"
                    ),
                    "limit": 50,
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["status"]
                in {
                    "SUCCESS",
                    "PARTIAL",
                }
            )

            assert (
                payload[
                    "captured_snapshots"
                ]
                >= 1
            )

            print("[PASS] Atualização manual")
            print(
                "       Snapshots:",
                payload.get(
                    "captured_snapshots"
                ),
            )
            print(
                "       Falhas:",
                len(
                    payload.get(
                        "failures",
                        [],
                    )
                ),
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Atualização:", exc)
            failed += 1

        try:
            response = client.get(
                "/real-markets/snapshots/latest"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1

            print("[PASS] Cache de snapshots")
            passed += 1

        except Exception as exc:
            print("[FAIL] Cache:", exc)
            failed += 1

        try:
            response = client.get(
                "/real-markets/dashboard"
            )
            response.raise_for_status()

            assert (
                "Núcleo de Dados de Mercado"
                in response.text
            )
            assert (
                "REFRESH-REAL-MARKET-DATA"
                in response.text
            )
            assert (
                response.headers.get(
                    "x-predarb-market-data-only"
                )
                == "true"
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
            print("[FAIL] Dashboard:", exc)
            failed += 1

        try:
            response = client.get(
                "/real-markets/architecture"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["phase"] == "9A"
            assert (
                "order_execution"
                in payload[
                    "deferred_to_next_phases"
                ]
            )

            print("[PASS] Arquitetura e escopo")
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
