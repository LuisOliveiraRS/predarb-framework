from __future__ import annotations

from typing import Any

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.shadow_execution_repository import (
    shadow_execution_audit_repository,
)
from app.paper.shadow_execution_simulator import (
    shadow_execution_simulator,
)


router = APIRouter(
    prefix="/real-markets/shadow-execution",
    tags=[
        "shadow-execution-read-only",
    ],
)


def _safe_flags() -> dict[str, Any]:
    return {
        "shadow_execution": True,
        "simulation_only": True,
        "market_data_only": True,
        "read_only_market_access": True,
        "audit_read_only": True,
        "simulation_endpoint_available": False,
        "audit_write_endpoint_available": False,
        "automatic_persistence": False,
        "order_submission_available": False,
        "automatic_execution_authorized": False,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


def _safe_audit_status() -> dict[str, Any]:
    try:
        return (
            shadow_execution_audit_repository
            .status()
        )

    except (
        OSError,
        ValueError,
    ) as exc:
        return {
            "status": "INVALID",
            "error": str(exc),
            "path": str(
                shadow_execution_audit_repository
                .path
            ),
            **_safe_flags(),
        }


@router.get("/health")
async def shadow_execution_health():
    simulator = (
        shadow_execution_simulator
        .status()
    )

    audit = _safe_audit_status()

    audit_healthy = (
        audit.get("status")
        in {
            "READY",
            "VALID",
        }
    )

    return {
        "status": (
            "healthy"
            if audit_healthy
            else "degraded"
        ),
        "phase": "9E",
        "name": "Shadow Execution",
        "simulator": simulator,
        "audit": audit,
        **_safe_flags(),
    }


@router.get("/status")
async def shadow_execution_status():
    return {
        "phase": "9E",
        "simulator": (
            shadow_execution_simulator
            .status()
        ),
        **_safe_flags(),
    }


@router.get("/audit/status")
async def shadow_audit_status():
    return {
        "phase": "9E",
        "audit": _safe_audit_status(),
        **_safe_flags(),
    }


@router.get("/audit/integrity")
async def shadow_audit_integrity():
    try:
        integrity = (
            shadow_execution_audit_repository
            .verify_integrity()
        )

    except (
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Falha ao verificar a auditoria "
                f"Shadow: {exc}"
            ),
        ) from exc

    return {
        "phase": "9E",
        "integrity": integrity,
        **_safe_flags(),
    }


@router.get("/audit/records")
async def shadow_audit_records(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
    newest_first: bool = Query(
        default=True,
    ),
):
    try:
        records = (
            shadow_execution_audit_repository
            .all(
                limit=limit,
                newest_first=newest_first,
            )
        )

        total_records = (
            shadow_execution_audit_repository
            .count()
        )

    except (
        OSError,
        ValueError,
    ) as exc:
        raise HTTPException(
            status_code=409,
            detail=(
                "Falha ao consultar a auditoria "
                f"Shadow: {exc}"
            ),
        ) from exc

    return {
        "phase": "9E",
        "count": len(records),
        "total_records": total_records,
        "limit": limit,
        "newest_first": newest_first,
        "records": records,
        **_safe_flags(),
    }


@router.get("/architecture")
async def shadow_execution_architecture():
    return {
        "phase": "9E",
        "name": "Shadow Execution",
        "components": [
            "immutable_shadow_models",
            "real_snapshot_reference",
            "economic_parity_guard",
            "simulated_order_intent",
            "simulated_fill_model",
            "fee_and_slippage_accounting",
            "append_only_audit_repository",
            "sha256_hash_chain",
            "integrity_verification",
            "read_only_api",
        ],
        "requirements": {
            "manual_match_required": True,
            "profitable_evaluation_required": True,
            "open_market_required": True,
            "snapshot_price_parity_required": True,
        },
        "available_endpoints": [
            "health",
            "status",
            "audit_status",
            "audit_integrity",
            "audit_records",
            "architecture",
        ],
        "explicitly_excluded": [
            "simulation_trigger_endpoint",
            "automatic_shadow_session",
            "automatic_audit_persistence",
            "order_submission",
            "order_cancellation",
            "exchange_adapter_access",
            "oms_access",
            "wallet_access",
            "balance_access",
            "private_keys",
            "credentials",
            "financial_authorization",
            "live_execution",
        ],
        **_safe_flags(),
    }
