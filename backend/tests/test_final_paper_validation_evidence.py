from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.final_paper_validation_evidence import (
    FinalPaperValidationEvidence,
)


def report(
    *,
    status="PAPER_VALIDATED",
    score=100,
):
    return {
        "status": status,
        "validated": status == "PAPER_VALIDATED",
        "scope": "PAPER_VALIDATION_ONLY",
        "generated_at": "2026-07-28T12:00:00+00:00",
        "validation_score": score,
        "thresholds": {"min_gate_evaluations": 3},
        "summary": {
            "total_checks": 9,
            "passed_checks": 9 if status == "PAPER_VALIDATED" else 6,
            "failed_checks": 0 if status == "PAPER_VALIDATED" else 3,
            "failed_data_checks": 0,
            "failed_validation_checks": (
                0 if status == "PAPER_VALIDATED" else 3
            ),
            "assurance_status": "ASSURED",
            "assurance_score": 100,
            "gate_status": "QUALIFIED",
            "gate_score": 100,
            "gate_history_entries": 3,
            "gate_history_latest_status": "QUALIFIED",
            "qualified_streak": 3,
            "total_runtime_failures": 0,
        },
        "checks": [],
        "failures": (
            []
            if status == "PAPER_VALIDATED"
            else [{"code": "QUALIFIED_STREAK"}]
        ),
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


def test_empty_archive_is_valid_and_safe(tmp_path):
    evidence = FinalPaperValidationEvidence(
        tmp_path / "evidence.json"
    )

    integrity = evidence.verify()

    assert integrity["integrity_status"] == "EMPTY"
    assert integrity["valid"] is True
    assert integrity["live_authorization"] is False
    assert integrity["next_step_authorized"] is False


def test_capture_creates_hash_chain(tmp_path):
    evidence = FinalPaperValidationEvidence(
        tmp_path / "evidence.json"
    )

    first = evidence.capture(report())
    second = evidence.capture(
        report(status="PAPER_PENDING", score=75)
    )

    assert first["evidence"]["previous_hash"] is None
    assert second["evidence"]["previous_hash"] == (
        first["evidence"]["entry_hash"]
    )

    integrity = evidence.verify()

    assert integrity["integrity_status"] == "VALID"
    assert integrity["entry_count"] == 2
    assert integrity["chain_head"] == (
        second["evidence"]["entry_hash"]
    )


def test_tampering_is_detected(tmp_path):
    path = tmp_path / "evidence.json"
    evidence = FinalPaperValidationEvidence(path)
    evidence.capture(report())

    state = json.loads(path.read_text(encoding="utf-8"))
    state["entries"][0]["validation_score"] = 1
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    integrity = evidence.verify()

    assert integrity["integrity_status"] == "BROKEN"
    assert integrity["valid"] is False


def test_capture_is_blocked_after_tampering(tmp_path):
    path = tmp_path / "evidence.json"
    evidence = FinalPaperValidationEvidence(path)
    evidence.capture(report())

    state = json.loads(path.read_text(encoding="utf-8"))
    state["entries"][0]["status"] = "PAPER_BLOCKED"
    path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    with pytest.raises(RuntimeError, match="corrompido"):
        evidence.capture(report())


def test_archive_does_not_truncate_chain(tmp_path):
    evidence = FinalPaperValidationEvidence(
        tmp_path / "evidence.json",
        max_entries=1,
    )

    evidence.capture(report())

    with pytest.raises(RuntimeError, match="limite"):
        evidence.capture(report())


def test_capture_rejects_next_step_authorization(tmp_path):
    evidence = FinalPaperValidationEvidence(
        tmp_path / "evidence.json"
    )

    unsafe = report()
    unsafe["next_step_authorized"] = True

    with pytest.raises(ValueError, match="next_step_authorized"):
        evidence.capture(unsafe)


def test_dashboard_and_exports_are_safe(tmp_path, monkeypatch):
    from app.api.routers import (
        paper_final_validation_evidence as router_module,
    )

    path = tmp_path / "evidence.json"

    monkeypatch.setenv(
        "PAPER_FINAL_VALIDATION_EVIDENCE_PATH",
        str(path),
    )

    FinalPaperValidationEvidence(path).capture(report())

    dashboard = asyncio.run(
        router_module.final_validation_evidence_dashboard()
    )

    assert (
        "Evidências da Validação Final Paper"
        in dashboard.body.decode("utf-8")
    )

    assert (
        dashboard.headers["x-predarb-next-step-authorization"]
        == "false"
    )

    csv_response = asyncio.run(
        router_module.final_validation_evidence_export_csv(
            limit=5000
        )
    )

    json_response = asyncio.run(
        router_module.final_validation_evidence_export_json()
    )

    assert "text/csv" in csv_response.headers["content-type"]

    payload = json.loads(
        json_response.body.decode("utf-8")
    )

    assert payload["integrity"]["integrity_status"] == "VALID"
    assert payload["next_step_authorized"] is False


def test_capture_endpoint_requires_confirmation():
    from fastapi import HTTPException
    from app.api.routers import (
        paper_final_validation_evidence as router_module,
    )

    with pytest.raises(HTTPException):
        asyncio.run(
            router_module.final_validation_evidence_capture(
                confirm="INVALID"
            )
        )


def test_application_registers_evidence_routes():
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.api.routers.paper_final_validation_evidence import router
    from app.core.application import create_app

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }

    required = {
        "/paper/final-validation/evidence/health",
        "/paper/final-validation/evidence/summary",
        "/paper/final-validation/evidence/verify",
        "/paper/final-validation/evidence/latest",
        "/paper/final-validation/evidence/entries",
        "/paper/final-validation/evidence/snapshot",
        "/paper/final-validation/evidence/capture",
        "/paper/final-validation/evidence/dashboard",
        "/paper/final-validation/evidence/export.csv",
        "/paper/final-validation/evidence/export.json",
    }

    assert not (required - paths)

    methods = {
        route.path: set(route.methods or set())
        for route in router.routes
    }

    assert methods[
        "/paper/final-validation/evidence/capture"
    ] == {"POST"}

    for path, method_set in methods.items():
        if path != "/paper/final-validation/evidence/capture":
            assert method_set == {"GET"}
