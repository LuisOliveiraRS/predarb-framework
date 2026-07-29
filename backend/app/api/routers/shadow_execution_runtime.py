from __future__ import annotations

from copy import deepcopy
from typing import Any

from fastapi import APIRouter

from app.paper.shadow_execution_runtime import (
    PROTECTED_FALSE_FLAGS,
    shadow_execution_runtime,
)


router = APIRouter(
    prefix="/real-markets/shadow-runtime",
    tags=["Phase 9F Shadow Runtime"],
)


def _validate_response_safety(
    payload: dict[str, Any],
) -> dict[str, Any]:
    unsafe = [
        flag
        for flag in PROTECTED_FALSE_FLAGS
        if payload.get(flag) is not False
    ]

    if unsafe:
        raise RuntimeError(
            "Resposta Shadow Runtime insegura: "
            + ", ".join(sorted(unsafe))
        )

    return payload


@router.get("/health")
async def shadow_runtime_health() -> dict[str, Any]:
    status = shadow_execution_runtime.status()

    payload = {
        "status": "healthy",
        "phase": "9F",
        "component": "shadow_execution_runtime",
        "runtime_status": status["status"],
        "runtime_mode": status["runtime_mode"],
        "manual_match_required": True,
        "profitable_evaluation_required": True,
        "scheduler_connected": (
            status["scheduler_connected"]
        ),
        "persistence_default": False,
        "paper_account_mutation": False,
        "exchange_imports": False,
        "oms_imports": False,
        "wallet_access": False,
        "credential_access": False,
        **{
            flag: status[flag]
            for flag in PROTECTED_FALSE_FLAGS
        },
    }

    return _validate_response_safety(
        payload
    )


@router.get("/status")
async def shadow_runtime_status() -> dict[str, Any]:
    payload = shadow_execution_runtime.status()

    return _validate_response_safety(
        payload
    )


@router.get("/metrics")
async def shadow_runtime_metrics() -> dict[str, Any]:
    status = shadow_execution_runtime.status()

    payload = {
        "status": status["status"],
        "phase": "9F",
        "cycle_count": status["cycle_count"],
        "completed_cycle_count": (
            status["completed_cycle_count"]
        ),
        "failed_cycle_count": (
            status["failed_cycle_count"]
        ),
        "skipped_cycle_count": (
            status["skipped_cycle_count"]
        ),
        "evaluated_opportunity_count": (
            status[
                "evaluated_opportunity_count"
            ]
        ),
        "eligible_opportunity_count": (
            status[
                "eligible_opportunity_count"
            ]
        ),
        "processed_opportunity_count": (
            status[
                "processed_opportunity_count"
            ]
        ),
        "simulated_count": (
            status["simulated_count"]
        ),
        "rejected_count": (
            status["rejected_count"]
        ),
        "error_count": status["error_count"],
        "last_cycle_id": (
            status["last_cycle_id"]
        ),
        "last_started_at": (
            status["last_started_at"]
        ),
        "last_completed_at": (
            status["last_completed_at"]
        ),
        "last_duration_ms": (
            status["last_duration_ms"]
        ),
        **{
            flag: status[flag]
            for flag in PROTECTED_FALSE_FLAGS
        },
    }

    return _validate_response_safety(
        payload
    )


@router.get("/last-cycle")
async def shadow_runtime_last_cycle() -> dict[str, Any]:
    status = shadow_execution_runtime.status()

    last_cycle = status.get(
        "last_cycle"
    )

    if last_cycle is None:
        payload = {
            "status": "NO_CYCLE_EXECUTED",
            "phase": "9F",
            "last_cycle": None,
            **{
                flag: status[flag]
                for flag in PROTECTED_FALSE_FLAGS
            },
        }

        return _validate_response_safety(
            payload
        )

    payload = {
        "status": "AVAILABLE",
        "phase": "9F",
        "last_cycle": deepcopy(
            last_cycle
        ),
        **{
            flag: status[flag]
            for flag in PROTECTED_FALSE_FLAGS
        },
    }

    return _validate_response_safety(
        payload
    )


@router.get("/architecture")
async def shadow_runtime_architecture() -> dict[str, Any]:
    status = shadow_execution_runtime.status()

    payload = {
        "status": "documented",
        "phase": "9F",
        "name": (
            "Shadow Runtime and "
            "Operational Validation"
        ),
        "flow": [
            "manual_confirmed_matches",
            "economic_evaluation",
            "profitable_filter",
            "shadow_simulation",
            "in_memory_runtime_metrics",
            "optional_append_only_audit",
        ],
        "read_only_endpoints": [
            "/health",
            "/status",
            "/metrics",
            "/last-cycle",
            "/architecture",
        ],
        "cycle_trigger_endpoint": False,
        "configuration_write_endpoint": False,
        "automatic_match_confirmation": False,
        "paper_account_mutation": False,
        "exchange_order_submission": False,
        "scheduler_connected": (
            status["scheduler_connected"]
        ),
        "persistence_default": False,
        "overlap_protection": True,
        "manual_match_required": True,
        "profitable_evaluation_required": True,
        "exchange_imports": False,
        "oms_imports": False,
        "wallet_access": False,
        "credential_access": False,
        **{
            flag: status[flag]
            for flag in PROTECTED_FALSE_FLAGS
        },
    }

    return _validate_response_safety(
        payload
    )
