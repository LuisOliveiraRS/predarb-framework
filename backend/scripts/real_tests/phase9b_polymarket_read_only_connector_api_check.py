from __future__ import annotations

import argparse

import httpx


BASE_PATH = (
    "/real-markets/polymarket"
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

    assert payload["read_only"] is True
    assert payload["market_data_only"] is True
    assert (
        payload["authentication_required"]
        is False
    )
    assert (
        payload["trading_endpoints_enabled"]
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
    first_market = None

    with httpx.Client(
        base_url=args.base_url.rstrip("/"),
        timeout=60,
    ) as client:
        try:
            response = client.get(
                f"{BASE_PATH}/configuration"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert (
                payload["connector"][
                    "connector_id"
                ]
                == "polymarket"
            )

            print(
                "[PASS] Configuração somente leitura"
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
                f"{BASE_PATH}/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            health = payload["health"]

            assert (
                health["connector_id"]
                == "polymarket"
            )

            if health["healthy"] is not True:
                raise AssertionError(
                    health.get("message")
                )

            print(
                "[PASS] APIs públicas acessíveis"
            )
            print(
                "       Mensagem:",
                health.get("message"),
            )
            print(
                "       Latência:",
                (
                    health.get("metadata")
                    or {}
                ).get("latency_ms"),
                "ms",
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Saúde externa:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                f"{BASE_PATH}/markets",
                params={
                    "limit": 10,
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["count"] >= 1

            first_market = (
                payload["markets"][0]
            )

            assert (
                first_market[
                    "connector_id"
                ]
                == "polymarket"
            )

            assert (
                len(
                    first_market[
                        "outcomes"
                    ]
                )
                >= 2
            )

            print(
                "[PASS] Mercados externos normalizados"
            )
            print(
                "       Quantidade:",
                payload.get("count"),
            )
            print(
                "       Primeiro:",
                first_market.get("title"),
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Mercados externos:",
                exc,
            )
            failed += 1

        try:
            assert first_market is not None

            response = client.get(
                (
                    f"{BASE_PATH}/markets/"
                    f"{first_market['market_id']}"
                    "/snapshot"
                )
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            snapshot = payload["snapshot"]

            assert (
                snapshot["market"][
                    "market_id"
                ]
                == first_market[
                    "market_id"
                ]
            )

            assert (
                len(
                    snapshot["quotes"]
                )
                >= 2
            )

            print(
                "[PASS] Orderbooks públicos normalizados"
            )

            for quote in snapshot["quotes"]:
                print(
                    "       ",
                    quote.get("outcome_id"),
                    "bid=",
                    quote.get("bid"),
                    "ask=",
                    quote.get("ask"),
                    "last=",
                    quote.get("last"),
                )

            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Snapshot externo:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/real-markets/connectors"
            )
            response.raise_for_status()

            payload = response.json()

            for field in (
                "paper_execution_authorized",
                "live_authorization",
                "execution_authorized",
                "live_execution",
                "financial_execution",
                "next_step_authorized",
            ):
                assert payload[field] is False

            assert any(
                item.get("connector_id")
                == "polymarket"
                for item in payload[
                    "connectors"
                ]
            )

            print(
                "[PASS] Registro consolidado"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Registro consolidado:",
                exc,
            )
            failed += 1

        try:
            response = client.get(
                "/real-markets/markets",
                params={
                    "connector_id": "polymarket",
                    "limit": 10,
                },
            )
            response.raise_for_status()

            payload = response.json()

            assert (
                payload["market_data_only"]
                is True
            )
            assert (
                payload["read_only"]
                is True
            )
            assert payload["count"] >= 1
            assert all(
                item["connector_id"]
                == "polymarket"
                for item in payload[
                    "markets"
                ]
            )

            print(
                "[PASS] Gateway consolidado"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Gateway:",
                exc,
            )
            failed += 1

        try:
            response = client.post(
                "/real-markets/refresh",
                params={
                    "confirm": (
                        "REFRESH-REAL-MARKET-DATA"
                    ),
                    "connector_id": (
                        "polymarket"
                    ),
                    "limit": 5,
                },
            )
            response.raise_for_status()

            payload = response.json()

            assert (
                payload["market_data_only"]
                is True
            )
            assert (
                payload["read_only"]
                is True
            )
            assert (
                payload["live_execution"]
                is False
            )
            assert (
                payload["captured_snapshots"]
                >= 1
            )

            print(
                "[PASS] Atualização manual externa"
            )
            print(
                "       Capturados:",
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
            print(
                "[FAIL] Atualização externa:",
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

            assert payload["phase"] == "9B"
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
                "[PASS] Escopo e proteções"
            )
            passed += 1

        except Exception as exc:
            print(
                "[FAIL] Arquitetura:",
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

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
