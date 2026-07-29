from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.certification_assurance_history_runtime import (
    paper_assurance_history_runtime,
)


router = APIRouter(
    prefix=(
        "/paper/certification/assurance/"
        "history-runtime"
    ),
    tags=[
        "paper-certification-assurance-history-runtime"
    ],
)


def _safe_response(
    payload,
):
    required_false = (
        "paper_execution_authorized",
        "live_authorization",
        "execution_authorized",
        "live_execution",
        "financial_execution",
    )

    for field in required_false:
        if payload.get(
            field
        ) is not False:
            raise RuntimeError(
                f"{field} não está "
                "explicitamente bloqueado."
            )

    return payload


@router.get("/health")
async def assurance_history_runtime_health():
    status = (
        paper_assurance_history_runtime
        .status()
    )

    return {
        "status": "healthy",
        "runtime": status,
        "manual_start_required": True,
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/status")
async def assurance_history_runtime_status():
    return _safe_response(
        paper_assurance_history_runtime
        .status()
    )


@router.get("/last-cycle")
async def assurance_history_runtime_last_cycle():
    status = (
        paper_assurance_history_runtime
        .status()
    )

    return {
        "last_result": (
            status["last_result"]
        ),
        "last_error": (
            status["last_error"]
        ),
        "last_cycle_at": (
            status["last_cycle_at"]
        ),
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.post("/cycle")
async def assurance_history_runtime_cycle(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-PAPER-CERTIFICATION-ASSURANCE"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-CERTIFICATION-ASSURANCE."
            ),
        )

    try:
        return _safe_response(
            await paper_assurance_history_runtime
            .capture_once()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/start")
async def assurance_history_runtime_start(
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
        != "START-PAPER-ASSURANCE-HISTORY-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "START-PAPER-ASSURANCE-HISTORY-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_assurance_history_runtime
            .start(
                interval_seconds=(
                    interval_seconds
                ),
                run_immediately=(
                    run_immediately
                ),
            )
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/stop")
async def assurance_history_runtime_stop(
    confirm: str = Query(...),
):
    if (
        confirm
        != "STOP-PAPER-ASSURANCE-HISTORY-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "STOP-PAPER-ASSURANCE-HISTORY-RUNTIME."
            ),
        )

    return _safe_response(
        await paper_assurance_history_runtime
        .stop()
    )


@router.post("/reset-statistics")
async def assurance_history_runtime_reset_statistics(
    confirm: str = Query(...),
):
    if (
        confirm
        != "RESET-PAPER-ASSURANCE-HISTORY-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "RESET-PAPER-ASSURANCE-HISTORY-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_assurance_history_runtime
            .reset_statistics()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
