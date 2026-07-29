from __future__ import annotations

import asyncio
import json

import pytest

from app.paper.stability_certification import (
    CertificationThresholds,
    PaperStabilityCertification,
)


def entry(
    status="READY",
    score=90,
):
    return {
        "id": f"{status}-{score}",
        "captured_at":
            "2026-07-28T12:00:00+00:00",
        "status": status,
        "readiness_score": score,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


class HistoryStub:
    def __init__(
        self,
        entries,
    ):
        self.entries = entries

    def summary(self):
        return {
            "total_entries": len(
                self.entries
            ),
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "read_only": True,
        }

    def list_entries(
        self,
        *,
        limit,
    ):
        return list(
            self.entries[:limit]
        )


def certification_for(entries):
    return PaperStabilityCertification(
        history=HistoryStub(entries),
        thresholds=CertificationThresholds(
            min_evaluations=5,
            min_consecutive_ready=3,
            recent_window=5,
            min_latest_score=80,
            min_recent_average_score=80,
            max_recent_not_ready=0,
        ),
    )


def test_certification_returns_no_data():
    report = certification_for(
        []
    ).evaluate()

    assert report["status"] == "NO_DATA"
    assert report["certified"] is False
    assert report["scope"] == "PAPER_ONLY"
    assert report["live_authorization"] is False


def test_certification_returns_pending():
    entries = [
        entry("READY", 90),
        entry("READY", 88),
    ]

    report = certification_for(
        entries
    ).evaluate()

    assert report["status"] == "PENDING"
    assert report["certified"] is False
    assert report["summary"][
        "consecutive_ready"
    ] == 2


def test_certification_returns_certified():
    entries = [
        entry("READY", 92),
        entry("READY", 90),
        entry("READY", 88),
        entry("READY", 86),
        entry("READY", 84),
    ]

    report = certification_for(
        entries
    ).evaluate()

    assert report["status"] == "CERTIFIED"
    assert report["certified"] is True
    assert report["summary"][
        "consecutive_ready"
    ] == 5
    assert report["summary"][
        "recent_not_ready"
    ] == 0
    assert report["live_authorization"] is False
    assert report[
        "paper_execution_authorized"
    ] is False


def test_certification_blocks_recent_not_ready():
    entries = [
        entry("READY", 92),
        entry("READY", 90),
        entry("READY", 88),
        entry("NOT_READY", 60),
        entry("READY", 84),
    ]

    report = certification_for(
        entries
    ).evaluate()

    assert report["status"] == "BLOCKED"
    assert any(
        item["code"]
        == "RECENT_NOT_READY_LIMIT"
        for item in report["blockers"]
    )


def test_certification_rejects_unsafe_history():
    unsafe = entry()
    unsafe["live_execution"] = True

    with pytest.raises(
        RuntimeError,
        match="history_entry",
    ):
        certification_for(
            [unsafe] * 5
        ).evaluate()


def test_dashboard_is_safe_html():
    from app.api.routers.paper_stability_certification import (
        paper_certification_dashboard,
    )

    response = asyncio.run(
        paper_certification_dashboard()
    )

    body = response.body.decode("utf-8")

    assert response.status_code == 200
    assert (
        "Certificação de Estabilidade Paper"
        in body
    )
    assert "Não autoriza execução live" in body
    assert "Avaliação somente leitura" in body
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_export_is_safe_json(
    monkeypatch,
):
    from app.api.routers import (
        paper_stability_certification
        as router_module,
    )

    expected = certification_for(
        [
            entry("READY", 92),
            entry("READY", 90),
            entry("READY", 88),
            entry("READY", 86),
            entry("READY", 84),
        ]
    ).evaluate()

    monkeypatch.setattr(
        router_module,
        "_report",
        lambda: expected,
    )

    response = asyncio.run(
        router_module
        .paper_certification_export_json()
    )

    payload = json.loads(
        response.body.decode("utf-8")
    )

    assert payload["status"] == "CERTIFIED"
    assert payload["live_authorization"] is False
    assert (
        response.headers[
            "x-predarb-live-authorization"
        ]
        == "false"
    )


def test_application_registers_certification_routes():
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.api.routers.paper_stability_certification import (
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
        "/paper/certification/health",
        "/paper/certification/report",
        "/paper/certification/dashboard",
        "/paper/certification/export.json",
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
