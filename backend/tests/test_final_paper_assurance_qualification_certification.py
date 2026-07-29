from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.final_paper_assurance_qualification_certification import (
    FinalPaperAssuranceQualificationCertification,
    FinalPaperQualificationCertificationCriteria,
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
    def __init__(
        self,
        payload,
    ):
        self.payload = payload

    def evaluate(self):
        return self.payload

    def summary(self):
        return self.payload

    def status(self):
        return self.payload


def gate_payload(
    *,
    status="QUALIFIED",
    score=100,
    critical_failures=0,
):
    return {
        "status": status,
        "qualified": (
            status == "QUALIFIED"
        ),
        "scope": (
            "PAPER_ASSURANCE_QUALIFICATION_ONLY"
        ),
        "qualification_score": score,
        "criteria": {},
        "summary": {
            "critical_failures": (
                critical_failures
            ),
        },
        "checks": [],
        "failures": [],
        **safe_flags(),
    }


def history_payload(
    *,
    total=3,
    latest="QUALIFIED",
    latest_score=100,
    average_score=100,
    streak_status="QUALIFIED",
    streak=3,
):
    return {
        "total_entries": total,
        "latest_status": latest,
        "latest_score": latest_score,
        "average_score": average_score,
        "current_streak_status": streak_status,
        "current_streak": streak,
        "longest_qualified_streak": streak,
        "transitions": 0,
        **safe_flags(),
    }


def runtime_payload(
    *,
    failures=0,
):
    return {
        "status": "STOPPED",
        "running": False,
        "failed_cycles": failures,
        **safe_flags(
            read_only=False
        ),
    }


def certification(
    *,
    gate=None,
    history=None,
    runtime=None,
):
    return (
        FinalPaperAssuranceQualificationCertification(
            gate_provider=ProviderStub(
                gate
                or gate_payload()
            ),
            gate_history_factory=lambda: ProviderStub(
                history
                or history_payload()
            ),
            gate_history_runtime=ProviderStub(
                runtime
                or runtime_payload()
            ),
            criteria=(
                FinalPaperQualificationCertificationCriteria(
                    min_gate_history_entries=3,
                    min_qualified_streak=3,
                    min_current_gate_score=90,
                    min_average_gate_score=90,
                    max_gate_runtime_failures=0,
                )
            ),
        )
    )


def test_certification_returns_certified():
    report = certification().evaluate()

    assert report["status"] == "CERTIFIED"
    assert report["certified"] is True
    assert report["certification_score"] == 100
    assert (
        report["scope"]
        == (
            "PAPER_QUALIFICATION_"
            "CERTIFICATION_ONLY"
        )
    )
    assert (
        report["next_step_authorized"]
        is False
    )


def test_certification_returns_no_data():
    report = certification(
        gate=gate_payload(
            status="NO_DATA",
            score=50,
        ),
        history=history_payload(
            total=0,
            latest="NO_DATA",
            latest_score=0,
            average_score=0,
            streak_status="NO_DATA",
            streak=0,
        ),
    ).evaluate()

    assert report["status"] == "NO_DATA"
    assert report["certified"] is False
    assert (
        report["certification_score"]
        <= 59
    )


def test_certification_returns_pending():
    report = certification(
        history=history_payload(
            total=3,
            latest="QUALIFIED",
            latest_score=100,
            average_score=85,
            streak_status="QUALIFIED",
            streak=2,
        ),
    ).evaluate()

    assert report["status"] == "PENDING"
    assert report["certified"] is False
    assert (
        report["certification_score"]
        <= 79
    )


def test_certification_blocks_gate_failure():
    report = certification(
        gate=gate_payload(
            status="BLOCKED",
            score=40,
            critical_failures=1,
        ),
        history=history_payload(
            total=3,
            latest="BLOCKED",
            latest_score=40,
            average_score=70,
            streak_status="BLOCKED",
            streak=1,
        ),
    ).evaluate()

    assert report["status"] == "BLOCKED"
    assert report["certified"] is False
    assert (
        report["certification_score"]
        <= 49
    )


def test_certification_rejects_unsafe_gate():
    unsafe = gate_payload()
    unsafe["live_execution"] = True

    with pytest.raises(
        RuntimeError,
        match="live_execution",
    ):
        certification(
            gate=unsafe
        ).evaluate()


def test_dashboard_and_export_are_safe(
    monkeypatch,
):
    from app.api.routers import (
        paper_final_assurance_qualification_certification
        as router_module,
    )

    expected = certification().evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    dashboard = asyncio.run(
        router_module
        .qualification_certification_dashboard()
    )

    body = dashboard.body.decode(
        "utf-8"
    )

    assert (
        "Certificação da Qualificação Final Paper"
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
        .qualification_certification_export_json()
    )

    payload = json.loads(
        exported.body.decode(
            "utf-8"
        )
    )

    assert (
        payload["status"]
        == "CERTIFIED"
    )
    assert (
        payload["next_step_authorized"]
        is False
    )


def test_health_is_safe(
    monkeypatch,
):
    from app.api.routers import (
        paper_final_assurance_qualification_certification
        as router_module,
    )

    expected = certification().evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    payload = asyncio.run(
        router_module
        .qualification_certification_health()
    )

    assert (
        payload["status"]
        == "CERTIFIED"
    )
    assert (
        payload["certified"]
        is True
    )
    assert (
        payload["next_step_authorized"]
        is False
    )
    assert payload["read_only"] is True


def test_application_registers_certification_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_assurance_qualification_certification import (
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
        (
            "/paper/final-assurance/"
            "qualification-certification/health"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/report"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/dashboard"
        ),
        (
            "/paper/final-assurance/"
            "qualification-certification/export.json"
        ),
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
