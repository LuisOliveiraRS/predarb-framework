from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.readiness_runtime import (
    paper_readiness_runtime,
)


router = APIRouter(
    prefix="/paper/readiness/runtime",
    tags=["paper-readiness-runtime"],
)


def _safe_response(
    payload,
):
    if (
        payload.get(
            "execution_authorized"
        )
        is not False
        or payload.get(
            "live_execution"
        )
        is not False
        or payload.get(
            "financial_execution"
        )
        is not False
    ):
        raise RuntimeError(
            "Guardas de segurança inválidas."
        )

    return payload


@router.get("/health")
async def readiness_runtime_health():
    status = (
        paper_readiness_runtime.status()
    )

    return {
        "status": "healthy",
        "runtime": status,
        "manual_start_required": True,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.get("/status")
async def readiness_runtime_status():
    return _safe_response(
        paper_readiness_runtime.status()
    )


@router.get("/last-cycle")
async def readiness_runtime_last_cycle():
    status = (
        paper_readiness_runtime.status()
    )

    return {
        "last_result": status[
            "last_result"
        ],
        "last_error": status[
            "last_error"
        ],
        "last_cycle_at": status[
            "last_cycle_at"
        ],
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
    }


@router.post("/cycle")
async def readiness_runtime_cycle(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-PAPER-READINESS"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-READINESS."
            ),
        )

    try:
        return _safe_response(
            await paper_readiness_runtime
            .capture_once()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/start")
async def readiness_runtime_start(
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
        != "START-PAPER-READINESS-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "START-PAPER-READINESS-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_readiness_runtime.start(
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
async def readiness_runtime_stop(
    confirm: str = Query(...),
):
    if (
        confirm
        != "STOP-PAPER-READINESS-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "STOP-PAPER-READINESS-RUNTIME."
            ),
        )

    return _safe_response(
        await paper_readiness_runtime.stop()
    )


@router.post("/reset-statistics")
async def readiness_runtime_reset_statistics(
    confirm: str = Query(...),
):
    if (
        confirm
        != "RESET-PAPER-READINESS-RUNTIME"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "RESET-PAPER-READINESS-RUNTIME."
            ),
        )

    try:
        return _safe_response(
            await paper_readiness_runtime
            .reset_statistics()
        )

    except RuntimeError as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc
