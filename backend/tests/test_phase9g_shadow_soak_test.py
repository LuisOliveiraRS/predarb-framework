from __future__ import annotations

import ast
import importlib.util
import json
from pathlib import Path
from typing import Any

import pytest


BACKEND_ROOT = Path(
    __file__
).resolve().parents[1]

SCRIPT_PATH = (
    BACKEND_ROOT
    / "scripts"
    / "real_tests"
    / "phase9g_shadow_soak_test.py"
)


def load_script():
    spec = importlib.util.spec_from_file_location(
        "phase9g_shadow_soak_test_under_test",
        SCRIPT_PATH,
    )

    if (
        spec is None
        or spec.loader is None
    ):
        raise RuntimeError(
            "Nao foi possivel carregar "
            "o script da Fase 9G."
        )

    module = importlib.util.module_from_spec(
        spec
    )

    spec.loader.exec_module(
        module
    )

    return module


phase9g = load_script()


class FakeResponse:
    def __init__(
        self,
        payload: dict[str, Any],
    ) -> None:
        self._payload = payload

    def raise_for_status(
        self,
    ) -> None:
        return None

    def json(
        self,
    ) -> dict[str, Any]:
        return self._payload


class FakeClient:
    def __init__(
        self,
        responses: dict[
            str,
            dict[str, Any],
        ],
    ) -> None:
        self.responses = responses
        self.calls: list[
            tuple[str, str]
        ] = []

    def get(
        self,
        path: str,
    ) -> FakeResponse:
        self.calls.append(
            (
                "GET",
                path,
            )
        )

        return FakeResponse(
            self.responses[path]
        )


def safe_payloads() -> dict[
    str,
    dict[str, Any],
]:
    safe_flags = {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "automatic_execution_authorized": False,
        "order_submission_available": False,
        "paper_account_mutation": False,
        "wallet_access": False,
        "credential_access": False,
    }

    return {
        phase9g.ENDPOINTS["health"]: {
            "status": "READY",
            "phase": "9F",
            "scheduler_connected": False,
            **safe_flags,
        },
        phase9g.ENDPOINTS["status"]: {
            "status": "READY",
            "phase": "9F",
            "scheduler_connected": False,
            "cycle_count": 2,
            "completed_cycle_count": 2,
            "failed_cycle_count": 0,
            "skipped_cycle_count": 0,
            "simulated_count": 1,
            "rejected_count": 1,
            "error_count": 0,
            "last_cycle_id": "cycle-2",
            "last_duration_ms": 12.5,
            "last_error": None,
            **safe_flags,
        },
        phase9g.ENDPOINTS["metrics"]: {
            "status": "READY",
            "phase": "9F",
            "cycle_count": 2,
            "completed_cycle_count": 2,
            "failed_cycle_count": 0,
            "skipped_cycle_count": 0,
            "simulated_count": 1,
            "rejected_count": 1,
            "error_count": 0,
            "last_cycle_id": "cycle-2",
            "last_duration_ms": 12.5,
            **safe_flags,
        },
        phase9g.ENDPOINTS["last_cycle"]: {
            "status": "AVAILABLE",
            "phase": "9F",
            "last_cycle": {
                "status": "COMPLETED",
            },
            **safe_flags,
        },
        phase9g.ENDPOINTS["architecture"]: {
            "status": "READY",
            "phase": "9F",
            "cycle_trigger_endpoint": False,
            "configuration_write_endpoint": False,
            "automatic_match_confirmation": False,
            **safe_flags,
        },
    }


def sample(
    *,
    cycle_count: int,
) -> dict[str, Any]:
    return {
        "captured_at": (
            "2026-07-29T18:40:00+00:00"
        ),
        "runtime_status": "READY",
        "phase": "9F",
        "scheduler_connected": False,
        "cycle_count": cycle_count,
        "completed_cycle_count": (
            cycle_count
        ),
        "failed_cycle_count": 0,
        "skipped_cycle_count": 0,
        "simulated_count": 0,
        "rejected_count": 0,
        "error_count": 0,
        "last_cycle_id": None,
        "last_cycle_status": (
            "NO_CYCLE_EXECUTED"
        ),
        "last_duration_ms": 0.0,
        "last_error": None,
        "latency_health_ms": 1.0,
        "latency_status_ms": 1.0,
        "latency_metrics_ms": 1.0,
        "latency_last_cycle_ms": 1.0,
        "latency_architecture_ms": 1.0,
    }


def test_file_state_handles_absent_and_present_file(
    tmp_path,
):
    path = (
        tmp_path
        / "artifact.json"
    )

    absent = phase9g.file_state(
        path
    )

    assert absent == {
        "exists": False,
        "size": None,
        "sha256": None,
    }

    path.write_text(
        '{"safe": true}',
        encoding="utf-8",
    )

    present = phase9g.file_state(
        path
    )

    assert present["exists"] is True
    assert present["size"] > 0
    assert len(
        present["sha256"]
    ) == 64


def test_safety_validation_accepts_false_flags():
    payload = safe_payloads()

    violations = (
        phase9g.truthy_safety_violations(
            payload
        )
    )

    assert violations == []


def test_safety_validation_detects_nested_true_flag():
    payload = {
        "nested": {
            "financial_execution": True,
        },
    }

    violations = (
        phase9g.truthy_safety_violations(
            payload
        )
    )

    assert violations == [
        "$.nested.financial_execution=True",
    ]


def test_capture_bundle_uses_only_get():
    responses = safe_payloads()

    client = FakeClient(
        responses
    )

    monitor = (
        phase9g.Phase9GShadowSoakMonitor(
            client=client,
            duration_seconds=1,
            poll_seconds=1,
            allow_idle=True,
        )
    )

    bundle = monitor.capture_bundle()

    assert [
        method
        for method, _ in client.calls
    ] == [
        "GET",
        "GET",
        "GET",
        "GET",
        "GET",
    ]

    assert [
        path
        for _, path in client.calls
    ] == list(
        phase9g.ENDPOINTS.values()
    )

    assert set(
        bundle["payloads"]
    ) == set(
        phase9g.ENDPOINTS
    )

    assert set(
        bundle["latency_ms"]
    ) == set(
        phase9g.ENDPOINTS
    )


def test_compact_sample_maps_runtime_metrics():
    monitor = (
        phase9g.Phase9GShadowSoakMonitor(
            client=FakeClient(
                safe_payloads()
            ),
            duration_seconds=1,
            poll_seconds=1,
            allow_idle=True,
        )
    )

    bundle = monitor.capture_bundle()

    compact = monitor.compact_sample(
        bundle
    )

    assert compact["runtime_status"] == "READY"
    assert compact["phase"] == "9F"
    assert compact["cycle_count"] == 2

    assert (
        compact["completed_cycle_count"]
        == 2
    )

    assert compact["simulated_count"] == 1
    assert compact["rejected_count"] == 1

    assert (
        compact["last_cycle_status"]
        == "COMPLETED"
    )

    assert compact["last_duration_ms"] == 12.5


def test_build_result_approves_progress():
    monitor = (
        phase9g.Phase9GShadowSoakMonitor(
            client=FakeClient(
                safe_payloads()
            ),
            duration_seconds=10,
            poll_seconds=1,
            allow_idle=False,
        )
    )

    monitor.samples = [
        sample(
            cycle_count=1,
        ),
        sample(
            cycle_count=3,
        ),
    ]

    monitor.audit_before = {
        "exists": False,
    }
    monitor.audit_after = {
        "exists": False,
    }

    monitor.paper_before = {
        "exists": True,
        "sha256": "same",
    }
    monitor.paper_after = {
        "exists": True,
        "sha256": "same",
    }

    result = monitor.build_result()

    assert result["approved"] is True
    assert result["deltas"]["cycle_count"] == 2

    assert all(
        result["criteria"].values()
    )

    assert result["safety_violations"] == []


def test_build_result_rejects_idle_without_permission():
    monitor = (
        phase9g.Phase9GShadowSoakMonitor(
            client=FakeClient(
                safe_payloads()
            ),
            duration_seconds=10,
            poll_seconds=1,
            allow_idle=False,
        )
    )

    monitor.samples = [
        sample(
            cycle_count=2,
        ),
        sample(
            cycle_count=2,
        ),
    ]

    monitor.audit_before = {
        "exists": False,
    }
    monitor.audit_after = {
        "exists": False,
    }
    monitor.paper_before = {
        "exists": True,
    }
    monitor.paper_after = {
        "exists": True,
    }

    result = monitor.build_result()

    assert result["approved"] is False

    assert (
        result["criteria"][
            "cycle_progress"
        ]
        is False
    )

    assert any(
        "Nenhum novo ciclo Shadow"
        in note
        for note in result["notes"]
    )


def test_execute_writes_reports_without_mutating_artifacts(
    tmp_path,
    monkeypatch,
):
    reports = (
        tmp_path
        / "reports"
    )

    audit = (
        tmp_path
        / "shadow_audit.jsonl"
    )

    paper = (
        tmp_path
        / "paper_account.json"
    )

    paper.write_text(
        '{"balance": 10000}',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        phase9g,
        "REPORT_DIR",
        reports,
    )
    monkeypatch.setattr(
        phase9g,
        "SHADOW_AUDIT_PATH",
        audit,
    )
    monkeypatch.setattr(
        phase9g,
        "PAPER_ACCOUNT_PATH",
        paper,
    )

    monitor = (
        phase9g.Phase9GShadowSoakMonitor(
            client=FakeClient(
                safe_payloads()
            ),
            duration_seconds=1,
            poll_seconds=1,
            allow_idle=True,
        )
    )

    def fake_monitoring():
        monitor.samples.append(
            sample(
                cycle_count=0,
            )
        )

        monitor.append_event(
            {
                "captured_at": (
                    "2026-07-29T18:40:00+00:00"
                ),
                "payloads": {},
                "latency_ms": {},
            }
        )

    monkeypatch.setattr(
        monitor,
        "run_monitoring",
        fake_monitoring,
    )

    exit_code = monitor.execute()

    assert exit_code == 0

    assert monitor.report_path.exists()
    assert monitor.samples_path.exists()
    assert monitor.events_path.exists()

    report = json.loads(
        monitor.report_path.read_text(
            encoding="utf-8"
        )
    )

    assert report["approved"] is True

    assert (
        report["artifacts"][
            "paper_account_before"
        ]
        == report["artifacts"][
            "paper_account_after"
        ]
    )

    assert (
        report["artifacts"][
            "shadow_audit_before"
        ]
        == report["artifacts"][
            "shadow_audit_after"
        ]
    )

    assert audit.exists() is False


def test_script_has_no_write_http_methods_or_live_imports():
    source = SCRIPT_PATH.read_text(
        encoding="utf-8"
    )

    tree = ast.parse(
        source
    )

    blocked_attributes = {
        "post",
        "put",
        "patch",
        "delete",
        "submit_order",
        "send_order",
    }

    blocked_modules = (
        "app.exchanges",
        "app.orders",
        "app.oms",
        "app.trading",
    )

    for node in ast.walk(tree):
        if isinstance(
            node,
            ast.Attribute,
        ):
            assert (
                node.attr
                not in blocked_attributes
            )

        if isinstance(
            node,
            ast.Import,
        ):
            for alias in node.names:
                assert not alias.name.startswith(
                    blocked_modules
                )

        if isinstance(
            node,
            ast.ImportFrom,
        ):
            module = node.module or ""

            assert not module.startswith(
                blocked_modules
            )
