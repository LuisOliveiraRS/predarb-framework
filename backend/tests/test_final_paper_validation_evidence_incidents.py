from __future__ import annotations

import asyncio

import pytest

from app.paper.final_paper_validation_evidence_incidents import (
    FinalPaperEvidenceIncidentJournal,
)


def safe_flags():
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


def alert(
    code="CHAIN_BROKEN",
    severity="critical",
    title="Cadeia corrompida",
):
    return {
        "code": code,
        "severity": severity,
        "title": title,
        "message": "Mensagem do alerta",
        "current_value": "BROKEN",
        "expected_value": "VALID",
    }


class MonitorStub:
    def __init__(self, alerts=None, unsafe=False):
        self.alerts = list(alerts or [])
        self.unsafe = unsafe

    def evaluate(self):
        payload = {
            "status": (
                "CRITICAL"
                if any(item["severity"] == "critical" for item in self.alerts)
                else ("WARNING" if self.alerts else "HEALTHY")
            ),
            "score": (
                49
                if any(item["severity"] == "critical" for item in self.alerts)
                else (79 if self.alerts else 100)
            ),
            "summary": {
                "total_entries": 1,
                "integrity_status": "VALID",
                "latest_status": "PAPER_VALIDATED",
                "critical_alerts": sum(
                    1
                    for item in self.alerts
                    if item["severity"] == "critical"
                ),
                "warning_alerts": sum(
                    1
                    for item in self.alerts
                    if item["severity"] == "warning"
                ),
                "info_alerts": sum(
                    1
                    for item in self.alerts
                    if item["severity"] == "info"
                ),
            },
            "alerts": self.alerts,
            **safe_flags(),
        }

        if self.unsafe:
            payload["next_step_authorized"] = True

        return payload


def journal_for(tmp_path, monitor):
    return FinalPaperEvidenceIncidentJournal(
        tmp_path / "incidents.json",
        monitor=monitor,
        max_snapshots=100,
    )


def test_empty_journal_is_safe(tmp_path):
    journal = journal_for(tmp_path, MonitorStub())

    summary = journal.summary()

    assert summary["total_incidents"] == 0
    assert summary["active_incidents"] == 0
    assert summary["next_step_authorized"] is False


def test_capture_creates_deterministic_incident(tmp_path):
    monitor = MonitorStub([alert()])
    journal = journal_for(tmp_path, monitor)

    first = journal.capture()
    incident_id = first["created"][0]

    second = journal.capture()

    assert second["created"] == []
    assert second["updated"] == [incident_id]

    incident = journal.get_incident(incident_id)

    assert incident["occurrences"] == 2
    assert incident["status"] == "ACTIVE"
    assert incident_id.startswith("fpe-")


def test_capture_resolves_and_reactivates_incident(tmp_path):
    monitor = MonitorStub([alert()])
    journal = journal_for(tmp_path, monitor)

    created = journal.capture()
    incident_id = created["created"][0]

    monitor.alerts = []
    resolved = journal.capture()

    assert resolved["resolved"] == [incident_id]
    assert journal.get_incident(incident_id)["status"] == "RESOLVED"

    monitor.alerts = [alert()]
    reactivated = journal.capture()

    assert reactivated["reactivated"] == [incident_id]

    incident = journal.get_incident(incident_id)

    assert incident["status"] == "ACTIVE"
    assert incident["reactivations"] == 1


def test_acknowledge_persists_operator(tmp_path):
    journal = journal_for(tmp_path, MonitorStub([alert()]))

    result = journal.capture()
    incident_id = result["created"][0]

    acknowledged = journal.acknowledge(
        incident_id,
        operator="operador-teste",
    )

    assert acknowledged["status"] == "acknowledged"
    assert (
        acknowledged["incident"]["acknowledged_by"]
        == "operador-teste"
    )
    assert acknowledged["incident"]["acknowledged_at"]


def test_capture_persists_monitor_snapshot(tmp_path):
    journal = journal_for(
        tmp_path,
        MonitorStub(
            [
                alert(
                    code="STALE_EVIDENCE",
                    severity="warning",
                    title="Evidência desatualizada",
                )
            ]
        ),
    )

    journal.capture()
    snapshots = journal.list_snapshots()

    assert len(snapshots) == 1
    assert snapshots[0]["monitor_status"] == "WARNING"
    assert snapshots[0]["alert_codes"] == ["STALE_EVIDENCE"]


def test_unsafe_monitor_is_rejected(tmp_path):
    journal = journal_for(
        tmp_path,
        MonitorStub([alert()], unsafe=True),
    )

    with pytest.raises(RuntimeError, match="evidence_monitor"):
        journal.capture()


def test_capture_endpoint_requires_confirmation():
    from fastapi import HTTPException
    from app.api.routers import (
        paper_final_validation_evidence_incidents as router_module,
    )

    with pytest.raises(HTTPException):
        asyncio.run(
            router_module.final_evidence_incidents_capture(
                confirm="INVALID"
            )
        )


def test_ack_endpoint_returns_not_found():
    from fastapi import HTTPException
    from app.api.routers import (
        paper_final_validation_evidence_incidents as router_module,
    )

    with pytest.raises(HTTPException) as exc:
        asyncio.run(
            router_module.final_evidence_incident_acknowledge(
                "missing",
                confirm="ACK-FINAL-PAPER-EVIDENCE-INCIDENT",
                operator="test",
            )
        )

    assert exc.value.status_code == 404


def test_application_registers_incident_routes():
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.api.routers.paper_final_validation_evidence_incidents import router
    from app.core.application import create_app

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }

    required = {
        "/paper/final-validation/evidence/incidents/health",
        "/paper/final-validation/evidence/incidents/summary",
        "/paper/final-validation/evidence/incidents/active",
        "/paper/final-validation/evidence/incidents/history",
        "/paper/final-validation/evidence/incidents/snapshots",
        "/paper/final-validation/evidence/incidents/capture",
        "/paper/final-validation/evidence/incidents/{incident_id}",
        "/paper/final-validation/evidence/incidents/{incident_id}/acknowledge",
    }

    assert not (required - paths)

    methods = {
        route.path: set(route.methods or set())
        for route in router.routes
    }

    assert methods[
        "/paper/final-validation/evidence/incidents/capture"
    ] == {"POST"}

    assert methods[
        "/paper/final-validation/evidence/incidents/{incident_id}/acknowledge"
    ] == {"POST"}
