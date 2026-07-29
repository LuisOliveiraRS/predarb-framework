from __future__ import annotations

import json

import pytest

from app.paper.performance_incidents import (
    PaperIncidentJournal,
)


def snapshot(
    alerts,
    *,
    status="WARNING",
    score=70,
):
    return {
        "status": status,
        "score": score,
        "alerts": alerts,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


def alert(
    *,
    code="FAILED_CYCLE_RATE_HIGH",
    severity="warning",
):
    return {
        "code": code,
        "severity": severity,
        "title": "Alerta de teste",
        "message": "Mensagem de teste",
        "current_value": 0.4,
        "threshold": 0.2,
    }


def test_empty_journal_is_safe(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    summary = journal.summary()

    assert summary["total_incidents"] == 0
    assert summary["active_incidents"] == 0
    assert summary["execution_authorized"] is False
    assert summary["live_execution"] is False


def test_capture_creates_active_incident(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    result = journal.capture(
        snapshot([alert()])
    )

    assert len(result["created"]) == 1
    assert result["summary"][
        "active_incidents"
    ] == 1

    active = journal.list_incidents(
        status="ACTIVE"
    )

    assert len(active) == 1
    assert active[0]["occurrences"] == 1


def test_capture_resolves_missing_alert(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    created = journal.capture(
        snapshot([alert()])
    )

    incident_id = created["created"][0]

    result = journal.capture(
        snapshot(
            [],
            status="HEALTHY",
            score=100,
        )
    )

    assert incident_id in result["resolved"]
    assert journal.summary()[
        "resolved_incidents"
    ] == 1


def test_resolved_incident_can_reactivate(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    first = journal.capture(
        snapshot([alert()])
    )

    incident_id = first["created"][0]

    journal.capture(
        snapshot(
            [],
            status="HEALTHY",
            score=100,
        )
    )

    result = journal.capture(
        snapshot([alert()])
    )

    assert incident_id in result["reactivated"]

    active = journal.list_incidents(
        status="ACTIVE"
    )

    assert active[0]["occurrences"] == 2
    assert active[0]["resolved_at"] is None


def test_acknowledge_marks_incident(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    captured = journal.capture(
        snapshot([alert()])
    )

    incident_id = captured["created"][0]

    result = journal.acknowledge(
        incident_id
    )

    assert result["incident"][
        "acknowledged_at"
    ]
    assert journal.summary()[
        "acknowledged_incidents"
    ] == 1


def test_capture_rejects_unsafe_snapshot(
    tmp_path,
):
    journal = PaperIncidentJournal(
        tmp_path / "incidents.json"
    )

    unsafe = snapshot([alert()])
    unsafe["live_execution"] = True

    with pytest.raises(ValueError):
        journal.capture(unsafe)


def test_state_is_persisted_as_safe_json(
    tmp_path,
):
    path = tmp_path / "incidents.json"

    journal = PaperIncidentJournal(path)
    journal.capture(
        snapshot(
            [
                alert(
                    code="SAFETY_VIOLATION",
                    severity="critical",
                )
            ],
            status="CRITICAL",
            score=50,
        )
    )

    payload = json.loads(
        path.read_text(encoding="utf-8")
    )

    assert payload[
        "execution_authorized"
    ] is False
    assert payload["live_execution"] is False
    assert len(payload["incidents"]) == 1


def test_application_registers_incident_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.core.application import create_app

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
        "/paper/performance/incidents/health",
        "/paper/performance/incidents/summary",
        "/paper/performance/incidents/active",
        "/paper/performance/incidents/history",
        "/paper/performance/incidents/snapshots",
        "/paper/performance/incidents/capture",
        "/paper/performance/incidents/{incident_id}/acknowledge",
    }

    assert not (
        required - paths
    )
