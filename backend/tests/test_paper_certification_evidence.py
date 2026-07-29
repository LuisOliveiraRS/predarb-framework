from __future__ import annotations

import asyncio
import csv
import io
import json

import pytest

from app.paper.certification_evidence import (
    PaperCertificationEvidence,
)


def certification_report(
    *,
    status="CERTIFIED",
    score=100,
):
    return {
        "status": status,
        "certified": status == "CERTIFIED",
        "scope": "PAPER_ONLY",
        "generated_at":
            "2026-07-28T12:00:00+00:00",
        "certification_score": score,
        "thresholds": {
            "min_evaluations": 5,
        },
        "summary": {
            "total_checks": 7,
            "passed_checks": 7,
            "pending_checks": 0,
            "blockers": 0,
            "total_history_entries": 8,
            "latest_status": "READY",
            "latest_score": 90,
            "recent_average_score": 88,
            "consecutive_ready": 4,
            "recent_not_ready": 0,
        },
        "checks": [],
        "blockers": [],
        "pending": [],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "manual_start_required": True,
        "read_only": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


def test_empty_archive_is_valid_and_safe(
    tmp_path,
):
    archive = PaperCertificationEvidence(
        tmp_path / "evidence.json"
    )

    verification = archive.verify()

    assert verification["status"] == "EMPTY"
    assert verification["valid"] is True
    assert verification[
        "live_authorization"
    ] is False


def test_capture_creates_hashed_evidence(
    tmp_path,
):
    archive = PaperCertificationEvidence(
        tmp_path / "evidence.json"
    )

    result = archive.capture(
        certification_report()
    )

    evidence = result["evidence"]

    assert evidence["status"] == "CERTIFIED"
    assert len(evidence["evidence_hash"]) == 64
    assert evidence["previous_hash"] == (
        archive.GENESIS_HASH
    )
    assert result["verification"][
        "status"
    ] == "VALID"


def test_second_capture_links_previous_hash(
    tmp_path,
):
    archive = PaperCertificationEvidence(
        tmp_path / "evidence.json"
    )

    first = archive.capture(
        certification_report(
            status="PENDING",
            score=70,
        )
    )["evidence"]

    second = archive.capture(
        certification_report()
    )["evidence"]

    assert second["previous_hash"] == (
        first["evidence_hash"]
    )
    assert archive.verify()["valid"] is True


def test_verification_detects_tampering(
    tmp_path,
):
    path = tmp_path / "evidence.json"
    archive = PaperCertificationEvidence(
        path
    )

    archive.capture(
        certification_report()
    )

    state = json.loads(
        path.read_text(
            encoding="utf-8"
        )
    )

    state["entries"][0][
        "certification_score"
    ] = 10

    path.write_text(
        json.dumps(
            state,
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )

    verification = archive.verify()

    assert verification["status"] == "BROKEN"
    assert verification["valid"] is False
    assert verification[
        "broken_reason"
    ] == "evidence_hash inválido"


def test_capture_rejects_live_authorization(
    tmp_path,
):
    archive = PaperCertificationEvidence(
        tmp_path / "evidence.json"
    )

    unsafe = certification_report()
    unsafe["live_authorization"] = True

    with pytest.raises(
        ValueError,
        match="live_authorization",
    ):
        archive.capture(unsafe)


def test_summary_counts_statuses(
    tmp_path,
):
    archive = PaperCertificationEvidence(
        tmp_path / "evidence.json"
    )

    archive.capture(
        certification_report(
            status="PENDING",
            score=70,
        )
    )

    archive.capture(
        certification_report(
            status="CERTIFIED",
            score=100,
        )
    )

    summary = archive.summary()

    assert summary["total_entries"] == 2
    assert summary["pending_entries"] == 1
    assert summary["certified_entries"] == 1
    assert summary["chain_valid"] is True


def test_dashboard_and_exports_are_safe(
    tmp_path,
    monkeypatch,
):
    from app.api.routers import (
        paper_certification_evidence
        as router_module,
    )

    evidence_path = (
        tmp_path / "evidence.json"
    )

    monkeypatch.setenv(
        "PAPER_CERTIFICATION_EVIDENCE_PATH",
        str(evidence_path),
    )

    PaperCertificationEvidence(
        evidence_path
    ).capture(
        certification_report()
    )

    dashboard = asyncio.run(
        router_module
        .certification_evidence_dashboard()
    )

    assert (
        "Evidências da Certificação"
        in dashboard.body.decode("utf-8")
    )

    assert (
        dashboard.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )

    csv_response = asyncio.run(
        router_module
        .certification_evidence_export_csv(
            limit=5000
        )
    )

    rows = list(
        csv.DictReader(
            io.StringIO(
                csv_response.body.decode(
                    "utf-8-sig"
                )
            )
        )
    )

    assert len(rows) == 1
    assert rows[0]["status"] == "CERTIFIED"

    json_response = asyncio.run(
        router_module
        .certification_evidence_export_json()
    )

    payload = json.loads(
        json_response.body.decode(
            "utf-8"
        )
    )

    assert payload["verification"][
        "valid"
    ] is True
    assert payload[
        "live_authorization"
    ] is False


def test_application_registers_evidence_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_evidence import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(
            app.routes
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/certification/evidence/health",
        "/paper/certification/evidence/summary",
        "/paper/certification/evidence/verify",
        "/paper/certification/evidence/latest",
        "/paper/certification/evidence/entries",
        "/paper/certification/evidence/snapshot",
        "/paper/certification/evidence/capture",
        "/paper/certification/evidence/dashboard",
        "/paper/certification/evidence/export.csv",
        "/paper/certification/evidence/export.json",
    }

    assert not (
        required - paths
    )

    methods = {
        route.path: set(
            route.methods or set()
        )
        for route in router.routes
    }

    assert methods[
        "/paper/certification/evidence/capture"
    ] == {"POST"}

    for path, method_set in methods.items():
        if path != (
            "/paper/certification/evidence/capture"
        ):
            assert method_set == {"GET"}
