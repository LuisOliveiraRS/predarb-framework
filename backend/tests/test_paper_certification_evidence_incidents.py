from __future__ import annotations

import asyncio

import pytest

from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)


def safe_snapshot(
    alerts=None,
    *,
    status="HEALTHY",
    score=100,
):
    alerts = alerts or []

    return {
        "status": status,
        "score": score,
        "generated_at":
            "2026-07-28T12:00:00+00:00",
        "alert_counts": {
            "critical": sum(
                1
                for item in alerts
                if item["severity"]
                == "critical"
            ),
            "warning": sum(
                1
                for item in alerts
                if item["severity"]
                == "warning"
            ),
            "info": sum(
                1
                for item in alerts
                if item["severity"]
                == "info"
            ),
        },
        "alerts": alerts,
        "diagnostics": {
            "total_entries": 2,
            "chain_status": "VALID",
            "chain_valid": True,
            "latest_status": "CERTIFIED",
        },
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


def warning_alert():
    return {
        "code": "EVIDENCE_STALE",
        "severity": "warning",
        "title": "Evidência desatualizada",
        "message": (
            "A evidência ultrapassou "
            "o limite de idade."
        ),
        "current_value": 100,
        "threshold": 72,
    }


def test_empty_journal_is_safe(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    summary = journal.summary()

    assert summary[
        "total_incidents"
    ] == 0
    assert summary[
        "active_incidents"
    ] == 0
    assert summary[
        "live_authorization"
    ] is False


def test_capture_creates_active_incident(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    result = journal.capture(
        safe_snapshot(
            [warning_alert()],
            status="WARNING",
            score=79,
        )
    )

    assert len(result["created"]) == 1
    assert result["summary"][
        "active_incidents"
    ] == 1

    incident = (
        journal.list_incidents(
            status="ACTIVE"
        )[0]
    )

    assert incident[
        "code"
    ] == "EVIDENCE_STALE"
    assert incident[
        "occurrences"
    ] == 1


def test_repeated_capture_updates_incident(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    snapshot = safe_snapshot(
        [warning_alert()],
        status="WARNING",
        score=79,
    )

    journal.capture(snapshot)
    result = journal.capture(
        snapshot
    )

    assert len(result["created"]) == 0
    assert len(result["updated"]) == 1

    incident = (
        journal.list_incidents(
            status="ACTIVE"
        )[0]
    )

    assert incident[
        "occurrences"
    ] == 2


def test_missing_alert_resolves_incident(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    journal.capture(
        safe_snapshot(
            [warning_alert()],
            status="WARNING",
            score=79,
        )
    )

    result = journal.capture(
        safe_snapshot()
    )

    assert len(result["resolved"]) == 1
    assert result["summary"][
        "active_incidents"
    ] == 0
    assert result["summary"][
        "resolved_incidents"
    ] == 1


def test_resolved_incident_reactivates(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    warning = safe_snapshot(
        [warning_alert()],
        status="WARNING",
        score=79,
    )

    journal.capture(warning)
    journal.capture(
        safe_snapshot()
    )
    result = journal.capture(
        warning
    )

    assert len(
        result["reactivated"]
    ) == 1

    incident = (
        journal.list_incidents(
            status="ACTIVE"
        )[0]
    )

    assert incident[
        "reactivations"
    ] == 1
    assert incident[
        "occurrences"
    ] == 2


def test_acknowledge_incident(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    created = journal.capture(
        safe_snapshot(
            [warning_alert()],
            status="WARNING",
            score=79,
        )
    )

    incident_id = (
        created["created"][0]
    )

    result = journal.acknowledge(
        incident_id,
        acknowledged_by="tester",
        note="Analisado.",
    )

    assert result[
        "status"
    ] == "acknowledged"
    assert result[
        "incident"
    ]["acknowledged"] is True
    assert result[
        "incident"
    ]["acknowledged_by"] == "tester"


def test_capture_rejects_unsafe_snapshot(
    tmp_path,
):
    journal = (
        PaperCertificationEvidenceIncidentJournal(
            tmp_path / "incidents.json"
        )
    )

    unsafe = safe_snapshot()
    unsafe[
        "live_authorization"
    ] = True

    with pytest.raises(
        ValueError,
        match="live_authorization",
    ):
        journal.capture(
            unsafe
        )


def test_application_registers_incident_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_certification_evidence_incidents import (
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
        "/paper/certification/evidence/incidents/health",
        "/paper/certification/evidence/incidents/summary",
        "/paper/certification/evidence/incidents/active",
        "/paper/certification/evidence/incidents/history",
        "/paper/certification/evidence/incidents/snapshots",
        "/paper/certification/evidence/incidents/{incident_id}",
        "/paper/certification/evidence/incidents/capture",
        "/paper/certification/evidence/incidents/{incident_id}/acknowledge",
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
        "/paper/certification/evidence/incidents/capture"
    ] == {"POST"}

    assert methods[
        "/paper/certification/evidence/incidents/{incident_id}/acknowledge"
    ] == {"POST"}

    for path, method_set in (
        methods.items()
    ):
        if path not in {
            "/paper/certification/evidence/incidents/capture",
            "/paper/certification/evidence/incidents/{incident_id}/acknowledge",
        }:
            assert method_set == {"GET"}
