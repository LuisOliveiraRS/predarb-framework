from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.final_paper_validation import (
    FinalPaperValidation,
    FinalPaperValidationThresholds,
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
    }

    if read_only:
        payload["read_only"] = True

    return payload


class AssuranceStub:
    def __init__(
        self,
        status="ASSURED",
        score=100,
    ):
        self.payload = {
            "status": status,
            "assured": (
                status == "ASSURED"
            ),
            "scope": "PAPER_ONLY",
            "assurance_score": score,
            **safe_flags(),
        }

    def snapshot(self):
        return self.payload


class GateStub:
    def __init__(
        self,
        status="QUALIFIED",
        score=100,
    ):
        self.payload = {
            "status": status,
            "qualified": (
                status == "QUALIFIED"
            ),
            "scope": "PAPER_ASSURANCE_ONLY",
            "qualification_score": score,
            "checks": [],
            "failures": [],
            **safe_flags(),
        }

    def evaluate(self):
        return self.payload


class HistoryStub:
    def __init__(
        self,
        *,
        total=3,
        latest="QUALIFIED",
        streak=3,
    ):
        self.payload = {
            "total_entries": total,
            "latest_status": latest,
            "current_streak": streak,
            **safe_flags(),
        }

    def summary(self):
        return self.payload


class RuntimeStub:
    def __init__(
        self,
        failures=0,
    ):
        self.payload = {
            "status": "STOPPED",
            "failed_cycles": failures,
            **safe_flags(
                read_only=False
            ),
        }

    def status(self):
        return self.payload


def validator(
    *,
    assurance_status="ASSURED",
    assurance_score=100,
    gate_status="QUALIFIED",
    gate_score=100,
    history_total=3,
    history_latest="QUALIFIED",
    history_streak=3,
    assurance_runtime_failures=0,
    gate_runtime_failures=0,
):
    return FinalPaperValidation(
        assurance_center=AssuranceStub(
            assurance_status,
            assurance_score,
        ),
        qualification_gate=GateStub(
            gate_status,
            gate_score,
        ),
        qualification_history=HistoryStub(
            total=history_total,
            latest=history_latest,
            streak=history_streak,
        ),
        assurance_runtime=RuntimeStub(
            assurance_runtime_failures
        ),
        gate_runtime=RuntimeStub(
            gate_runtime_failures
        ),
        thresholds=FinalPaperValidationThresholds(
            min_gate_evaluations=3,
            min_qualified_streak=3,
            min_gate_score=90,
            min_assurance_score=90,
            max_runtime_failures=0,
        ),
    )


def test_validation_returns_insufficient_data():
    report = validator(
        history_total=1,
        history_latest="INSUFFICIENT_DATA",
        history_streak=0,
    ).evaluate()

    assert (
        report["status"]
        == "INSUFFICIENT_DATA"
    )
    assert report["validated"] is False
    assert (
        report["next_step_authorized"]
        is False
    )


def test_validation_returns_paper_validated():
    report = validator().evaluate()

    assert (
        report["status"]
        == "PAPER_VALIDATED"
    )
    assert report["validated"] is True
    assert (
        report["scope"]
        == "PAPER_VALIDATION_ONLY"
    )
    assert (
        report["live_authorization"]
        is False
    )
    assert (
        report["next_step_authorized"]
        is False
    )


def test_validation_is_blocked_by_gate():
    report = validator(
        gate_status="NOT_QUALIFIED",
        gate_score=70,
    ).evaluate()

    assert (
        report["status"]
        == "PAPER_BLOCKED"
    )
    assert report["validated"] is False


def test_validation_is_blocked_by_runtime_failure():
    report = validator(
        gate_runtime_failures=1,
    ).evaluate()

    assert (
        report["status"]
        == "PAPER_BLOCKED"
    )
    assert (
        report["summary"][
            "total_runtime_failures"
        ]
        == 1
    )


def test_validation_rejects_unsafe_component():
    unsafe = AssuranceStub()
    unsafe.payload[
        "live_execution"
    ] = True

    validation = FinalPaperValidation(
        assurance_center=unsafe,
        qualification_gate=GateStub(),
        qualification_history=HistoryStub(),
        assurance_runtime=RuntimeStub(),
        gate_runtime=RuntimeStub(),
        thresholds=FinalPaperValidationThresholds(
            min_gate_evaluations=3,
            min_qualified_streak=3,
            min_gate_score=90,
            min_assurance_score=90,
            max_runtime_failures=0,
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="assurance",
    ):
        validation.evaluate()


def test_dashboard_is_safe_html():
    from app.api.routers.paper_final_validation import (
        final_paper_validation_dashboard,
    )

    response = asyncio.run(
        final_paper_validation_dashboard()
    )

    body = response.body.decode(
        "utf-8"
    )

    assert (
        "Validação Final Paper"
        in body
    )

    assert (
        "Não autoriza a próxima fase"
        in body
    )

    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )

    assert (
        response.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )


def test_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_final_validation
        as router_module,
    )

    expected = validator().evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    response = asyncio.run(
        router_module
        .final_paper_validation_export_json()
    )

    payload = json.loads(
        response.body.decode(
            "utf-8"
        )
    )

    assert (
        payload["status"]
        == "PAPER_VALIDATED"
    )

    assert (
        payload[
            "next_step_authorized"
        ]
        is False
    )

    assert (
        response.headers[
            "x-predarb-next-step-authorization"
        ]
        == "false"
    )


def test_application_registers_final_validation_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_final_validation import (
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
        "/paper/final-validation/health",
        "/paper/final-validation/report",
        "/paper/final-validation/dashboard",
        "/paper/final-validation/export.json",
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
