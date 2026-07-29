from __future__ import annotations

import argparse

import httpx


def ensure_safe(payload):
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
                "/paper/final-validation/evidence/incidents/health"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            print("[PASS] Saúde do diário")
            print("       Ativos:", payload.get("active_incidents"))
            print("       Resolvidos:", payload.get("resolved_incidents"))
            passed += 1

        except Exception as exc:
            print("[FAIL] Saúde:", exc)
            failed += 1

        try:
            response = client.post(
                "/paper/final-validation/evidence/incidents/capture",
                params={
                    "confirm": (
                        "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS"
                    ),
                },
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            assert payload["status"] == "captured"

            print("[PASS] Captura do monitor")
            print("       Criados:", len(payload.get("created") or []))
            print("       Atualizados:", len(payload.get("updated") or []))
            print("       Resolvidos:", len(payload.get("resolved") or []))
            passed += 1

        except Exception as exc:
            print("[FAIL] Captura:", exc)
            failed += 1

        for label, endpoint in (
            (
                "Resumo",
                "/paper/final-validation/evidence/incidents/summary",
            ),
            (
                "Incidentes ativos",
                "/paper/final-validation/evidence/incidents/active?limit=50",
            ),
            (
                "Histórico",
                "/paper/final-validation/evidence/incidents/history?limit=50",
            ),
            (
                "Snapshots",
                "/paper/final-validation/evidence/incidents/snapshots?limit=50",
            ),
        ):
            try:
                response = client.get(endpoint)
                response.raise_for_status()

                payload = response.json()
                ensure_safe(payload)

                print(f"[PASS] {label}")
                passed += 1

            except Exception as exc:
                print(f"[FAIL] {label}: {exc}")
                failed += 1

        try:
            response = client.post(
                "/paper/final-validation/"
                "evidence/incidents/missing/acknowledge",
                params={
                    "confirm": (
                        "ACK-FINAL-PAPER-EVIDENCE-INCIDENT"
                    ),
                    "operator": "api-check",
                },
            )

            assert response.status_code == 404

            print(
                "[PASS] Reconhecimento rejeita incidente inexistente"
            )
            passed += 1

        except Exception as exc:
            print("[FAIL] Reconhecimento:", exc)
            failed += 1

        try:
            response = client.get(
                "/paper/final-validation/"
                "evidence/incidents/history?limit=1"
            )
            response.raise_for_status()

            payload = response.json()
            ensure_safe(payload)

            incidents = payload.get("incidents") or []

            if incidents:
                incident_id = incidents[0]["id"]

                detail = client.get(
                    "/paper/final-validation/"
                    f"evidence/incidents/{incident_id}"
                )
                detail.raise_for_status()

                detail_payload = detail.json()
                ensure_safe(detail_payload)

                assert detail_payload["incident"]["id"] == incident_id

            print("[PASS] Consulta individual")
            passed += 1

        except Exception as exc:
            print("[FAIL] Consulta individual:", exc)
            failed += 1

    print()
    print("Aprovados:", passed)
    print("Falhas:", failed)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
