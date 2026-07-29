from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.final_paper_validation_evidence_incident_runtime import (
    final_paper_evidence_incident_runtime,
)


router = APIRouter(
    prefix=(
        "/paper/final-validation/"
        "evidence/incident-runtime"
    ),
    tags=[
        "paper-final-validation-evidence-incident-runtime"
    ],
)


def _safe_response(
    payload,
):
    for field in (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
        "next_step_authorized",
    ):
        if payload.get(field) is not False:
            raise RuntimeError(
                f"{field} não está explicitamente bloqueado."
            )

    return payload


@router.get("/health")
async def final_evidence_incident_runtime_health():
    return {
        "status": "healthy",
        "runtime": (
            final_paper_evidence_incident_runtime
            .status()
        ),
        "manual_start_required": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.get("/status")
async def final_evidence_incident_runtime_status():
    return _safe_response(
        final_paper_evidence_incident_runtime
        .status()
    )


@router.get("/last-cycle")
async def final_evidence_incident_runtime_last_cycle():
    status = (
        final_paper_evidence_incident_runtime
        .status()
    )

    return {
        "last_result": status["last_result"],
        "last_error": status["last_error"],
        "last_cycle_at": status["last_cycle_at"],
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
    }


@router.post("/cycle")
async def final_evidence_incident_runtime_cycle(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS."
            ),
        )

    try:
        return _safe_response(
            await final_paper_evidence_incident_runtime
            .capture_once()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/start")
async def final_evidence_incident_runtime_start(
    confirm: str = Query(...),
    interval_seconds: float = Query(
        default=300.0,
        ge=30.0,
        le=86400.0,
    ),
    run_immediately: bool = Query(
        default=True
    ),
):
    if (
        confirm
        != "START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "START-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await final_paper_evidence_incident_runtime
            .start(
                interval_seconds=interval_seconds,
                run_immediately=run_immediately,
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/stop")
async def final_evidence_incident_runtime_stop(
    confirm: str = Query(...),
):
    if (
        confirm
        != "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "STOP-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME."
            ),
        )

    return _safe_response(
        await final_paper_evidence_incident_runtime
        .stop()
    )


@router.post("/reset-statistics")
async def final_evidence_incident_runtime_reset_statistics(
    confirm: str = Query(...),
):
    if (
        confirm
        != "RESET-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "RESET-FINAL-PAPER-EVIDENCE-INCIDENT-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await final_paper_evidence_incident_runtime
            .reset_statistics()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
