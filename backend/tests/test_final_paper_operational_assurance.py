from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.final_paper_operational_assurance import (
    FinalPaperOperationalAssurance,
)


def safe_flags(
    *,
    read_only=True,
):
    payload = {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }

    if read_only:
        payload["read_only"] = True

    return payload


class ProviderStub:
    def __init__(self, payload):
        self.payload = payload

    def evaluate(self):
        return self.payload

    def status(self):
        return self.payload

    def summary(self):
        return self.payload

    def verify(self):
        return self.payload


class FailingProviderStub:
    def evaluate(self):
        raise RuntimeError("Falha simulada")


def validation_payload(
    *,
    status="PAPER_VALIDATED",
):
    return {
        "status": status,
        "validated": status == "PAPER_VALIDATED",
        "scope": "PAPER_VALIDATION_ONLY",
        "validation_score": (
            100
            if status == "PAPER_VALIDATED"
            else 50
        ),
        **safe_flags(),
    }


def history_payload(
    *,
    total=1,
):
    return {
        "total_entries": total,
        **safe_flags(),
    }


def runtime_payload(
    *,
    failures=0,
):
    return {
        "status": "STOPPED",
        "failed_cycles": failures,
        **safe_flags(
            read_only=False
        ),
    }


def evidence_summary_payload(
    *,
    total=1,
    integrity="VALID",
):
    return {
        "total_entries": total,
        "integrity_status": integrity,
        "chain_head": (
            "abc123"
            if total
            else None
        ),
        **safe_flags(),
    }


def evidence_integrity_payload(
    *,
    integrity="VALID",
):
    return {
        "integrity_status": integrity,
        "valid": integrity != "BROKEN",
        **safe_flags(),
    }


def monitor_payload(
    *,
    status="HEALTHY",
):
    return {
        "status": status,
        "score": (
            100
            if status == "HEALTHY"
            else 49
        ),
        "summary": {},
        "alerts": [],
        **safe_flags(),
    }


def journal_payload(
    *,
    active=0,
    critical=0,
):
    return {
        "active_incidents": active,
        "active_critical": critical,
        **safe_flags(),
    }


def assurance(
    *,
    validation_status="PAPER_VALIDATED",
    history_entries=1,
    evidence_entries=1,
    integrity_status="VALID",
    monitor_status="HEALTHY",
    active_incidents=0,
    active_critical=0,
    validation_runtime_failures=0,
    incident_runtime_failures=0,
):
    return FinalPaperOperationalAssurance(
        validation_provider=ProviderStub(
            validation_payload(
                status=validation_status
            )
        ),
        validation_history_factory=lambda: ProviderStub(
            history_payload(
                total=history_entries
            )
        ),
        validation_runtime=ProviderStub(
            runtime_payload(
                failures=validation_runtime_failures
            )
        ),
        evidence_factory=lambda: ProviderStub(
            evidence_summary_payload(
                total=evidence_entries,
                integrity=integrity_status,
            )
        ),
        evidence_monitor=ProviderStub(
            monitor_payload(
                status=monitor_status
            )
        ),
        incident_journal_factory=lambda: ProviderStub(
            journal_payload(
                active=active_incidents,
                critical=active_critical,
            )
        ),
        incident_runtime=ProviderStub(
            runtime_payload(
                failures=incident_runtime_failures
            )
        ),
    )


def test_assurance_returns_assured():
    report = assurance().evaluate()

    assert report["status"] == "ASSURED"
    assert report["assured"] is True
    assert report["assurance_score"] == 100
    assert report["scope"] == "PAPER_ASSURANCE_ONLY"
    assert report["next_step_authorized"] is False


def test_assurance_returns_no_data():
    report = assurance(
        history_entries=0,
        evidence_entries=0,
        validation_status="INSUFFICIENT_DATA",
        integrity_status="EMPTY",
        monitor_status="NO_DATA",
    ).evaluate()

    assert report["status"] == "NO_DATA"
    assert report["assured"] is False
    assert report["assurance_score"] <= 59


def test_assurance_blocks_broken_chain():
    report = assurance(
        integrity_status="BROKEN",
        monitor_status="CRITICAL",
        active_incidents=1,
        active_critical=1,
    ).evaluate()

    assert report["status"] == "BLOCKED"
    assert report["assured"] is False
    assert report["assurance_score"] <= 49


def test_assurance_warns_on_runtime_failures():
    report = assurance(
        validation_runtime_failures=1,
    ).evaluate()

    assert report["status"] == "WARNING"
    assert report["assured"] is False
    assert (
        report["summary"][
            "total_runtime_failures"
        ]
        == 1
    )


def test_assurance_blocks_component_error():
    instance = assurance()

    instance.validation_provider = (
        FailingProviderStub()
    )

    report = instance.evaluate()

    assert report["status"] == "BLOCKED"
    assert report["summary"]["component_errors"] == 1
    assert "validation" in report["component_errors"]


def test_assurance_rejects_unsafe_component():
    unsafe = validation_payload()
    unsafe["live_execution"] = True

    instance = assurance()
    instance.validation_provider = ProviderStub(
        unsafe
    )

    with pytest.raises(
        RuntimeError,
        match="validation",
    ):
        instance.evaluate()


def test_dashboard_and_export_are_safe(
    monkeypatch,
):
    from app.api.routers import (
        paper_final_operational_assurance
        as router_module,
    )

    expected = assurance().evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    dashboard = asyncio.run(
        router_module
        .final_paper_assurance_dashboard()
    )

    body = dashboard.body.decode(
        "utf-8"
    )

    assert (
        "Garantia Operacional Final Paper"
        in body
    )

    assert (
        "Próxima fase não autorizada"
        in body
    )

    assert (
        dashboard.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )

    exported = asyncio.run(
        router_module
        .final_paper_assurance_export_json()
    )

    payload = json.loads(
        exported.body.decode(
            "utf-8"
        )
    )

    assert payload["status"] == "ASSURED"
    assert payload["next_step_authorized"] is False


def test_application_registers_final_assurance_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_operational_assurance import (
        router,
    )
    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/final-assurance/health",
        "/paper/final-assurance/report",
        "/paper/final-assurance/dashboard",
        "/paper/final-assurance/export.json",
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

    assert all(
        method_set == {"GET"}
        for method_set in methods.values()
    )
