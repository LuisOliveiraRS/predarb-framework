from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query

from app.paper.final_paper_validation_evidence_incidents import (
    FinalPaperEvidenceIncidentJournal,
)


router = APIRouter(
    prefix="/paper/final-validation/evidence/incidents",
    tags=["paper-final-validation-evidence-incidents"],
)


def _journal() -> FinalPaperEvidenceIncidentJournal:
    return FinalPaperEvidenceIncidentJournal()


def _safe_base() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "next_step_authorized": False,
        "read_only": True,
    }


@router.get("/health")
async def final_evidence_incidents_health():
    summary = _journal().summary()

    return {
        "status": "healthy",
        "active_incidents": summary["active_incidents"],
        "resolved_incidents": summary["resolved_incidents"],
        "total_snapshots": summary["total_snapshots"],
        **_safe_base(),
    }


@router.get("/summary")
async def final_evidence_incidents_summary():
    return _journal().summary()


@router.get("/active")
async def final_evidence_incidents_active(
    limit: int = Query(default=500, ge=1, le=5000),
):
    incidents = _journal().list_incidents(
        status="ACTIVE",
        limit=limit,
    )

    return {
        "count": len(incidents),
        "incidents": incidents,
        **_safe_base(),
    }


@router.get("/history")
async def final_evidence_incidents_history(
    limit: int = Query(default=500, ge=1, le=5000),
):
    incidents = _journal().list_incidents(limit=limit)

    return {
        "count": len(incidents),
        "incidents": incidents,
        **_safe_base(),
    }


@router.get("/snapshots")
async def final_evidence_incidents_snapshots(
    limit: int = Query(default=500, ge=1, le=5000),
):
    snapshots = _journal().list_snapshots(limit=limit)

    return {
        "count": len(snapshots),
        "snapshots": snapshots,
        **_safe_base(),
    }


@router.post("/capture")
async def final_evidence_incidents_capture(
    confirm: str = Query(...),
):
    if confirm != "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-FINAL-PAPER-EVIDENCE-INCIDENTS."
            ),
        )

    try:
        return _journal().capture()
    except (RuntimeError, ValueError) as exc:
        raise HTTPException(
            status_code=409,
            detail=str(exc),
        ) from exc


@router.post("/{incident_id}/acknowledge")
async def final_evidence_incident_acknowledge(
    incident_id: str,
    confirm: str = Query(...),
    operator: str = Query(default="administrator"),
):
    if confirm != "ACK-FINAL-PAPER-EVIDENCE-INCIDENT":
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "ACK-FINAL-PAPER-EVIDENCE-INCIDENT."
            ),
        )

    try:
        return _journal().acknowledge(
            incident_id,
            operator=operator,
        )
    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail="Incidente não encontrado.",
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc


@router.get("/{incident_id}")
async def final_evidence_incident_get(
    incident_id: str,
):
    incident = _journal().get_incident(incident_id)

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail="Incidente não encontrado.",
        )

    return {
        "incident": incident,
        **_safe_base(),
    }
