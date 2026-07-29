from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.performance_incident_runtime import (
    paper_incident_runtime,
)


router = APIRouter(
    prefix="/paper/performance/incidents/runtime",
    tags=["paper-performance-incident-runtime"],
)


def _safe_response(
    payload,
):
    if (
        payload.get("execution_authorized")
        is not False
        or payload.get("live_execution")
        is not False
        or payload.get("financial_execution")
        is not False
    ):
        raise RuntimeError(
            "Guardas de segurança inválidas."
        )

    return payload


@router.get("/health")
async def incident_runtime_health():
    status = paper_incident_runtime.status()

    return {
        "status": "healthy",
        "runtime": status,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "manual_start_required": True,
    }


@router.get("/status")
async def incident_runtime_status():
    return _safe_response(
        paper_incident_runtime.status()
    )


@router.get("/last-cycle")
async def incident_runtime_last_cycle():
    status = paper_incident_runtime.status()

    return {
        "last_result": status["last_result"],
        "last_error": status["last_error"],
        "last_cycle_at": status[
            "last_cycle_at"
        ],
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.post("/cycle")
async def incident_runtime_cycle(
    confirm: str = Query(...),
):
    if confirm != "CAPTURE-PAPER-INCIDENTS":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-INCIDENTS."
            ),
        )

    try:
        return _safe_response(
            await paper_incident_runtime.capture_once()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/start")
async def incident_runtime_start(
    confirm: str = Query(...),
    interval_seconds: float = Query(
        default=60.0,
        ge=5.0,
        le=3600.0,
    ),
    run_immediately: bool = Query(
        default=True
    ),
):
    if confirm != "START-PAPER-INCIDENT-RUNTIME":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "START-PAPER-INCIDENT-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_incident_runtime.start(
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
async def incident_runtime_stop(
    confirm: str = Query(...),
):
    if confirm != "STOP-PAPER-INCIDENT-RUNTIME":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "STOP-PAPER-INCIDENT-RUNTIME."
            ),
        )

    return _safe_response(
        await paper_incident_runtime.stop()
    )


@router.post("/reset-statistics")
async def incident_runtime_reset_statistics(
    confirm: str = Query(...),
):
    if confirm != "RESET-PAPER-INCIDENT-RUNTIME":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "RESET-PAPER-INCIDENT-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_incident_runtime
            .reset_statistics()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
