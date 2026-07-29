from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.performance_incidents import (
    PaperIncidentJournal,
)
from app.paper.performance_monitor import (
    PaperPerformanceMonitor,
)


router = APIRouter(
    prefix="/paper/performance/incidents",
    tags=["paper-performance-incidents"],
)


def _journal() -> PaperIncidentJournal:
    return PaperIncidentJournal()


@router.get("/health")
async def incident_health():
    summary = _journal().summary()

    return {
        "status": "healthy",
        "journal_path": summary["journal_path"],
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/summary")
async def incident_summary():
    return _journal().summary()


@router.get("/active")
async def incident_active(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    incidents = _journal().list_incidents(
        status="ACTIVE",
        limit=limit,
    )

    return {
        "count": len(incidents),
        "incidents": incidents,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/history")
async def incident_history(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    incidents = _journal().list_incidents(
        limit=limit
    )

    return {
        "count": len(incidents),
        "incidents": incidents,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.get("/snapshots")
async def incident_snapshots(
    limit: int = Query(
        default=100,
        ge=1,
        le=1000,
    ),
):
    snapshots = _journal().snapshots(
        limit=limit
    )

    return {
        "count": len(snapshots),
        "snapshots": snapshots,
        "execution_authorized": False,
        "live_execution": False,
        "read_only": True,
    }


@router.post("/capture")
async def incident_capture(
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

    snapshot = PaperPerformanceMonitor().snapshot()

    return _journal().capture(snapshot)


@router.post(
    "/{incident_id}/acknowledge"
)
async def incident_acknowledge(
    incident_id: str,
    confirm: str = Query(...),
):
    if confirm != "ACK-PAPER-INCIDENT":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "ACK-PAPER-INCIDENT."
            ),
        )

    try:
        return _journal().acknowledge(
            incident_id
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Incidente não encontrado.",
        ) from exc
