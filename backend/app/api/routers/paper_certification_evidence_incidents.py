from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.certification_evidence_incidents import (
    PaperCertificationEvidenceIncidentJournal,
)
from app.paper.certification_evidence_monitor import (
    paper_certification_evidence_monitor,
)


router = APIRouter(
    prefix=(
        "/paper/certification/evidence/incidents"
    ),
    tags=[
        "paper-certification-evidence-incidents"
    ],
)


def _journal():
    return (
        PaperCertificationEvidenceIncidentJournal()
    )


def _safe_base() -> dict[str, bool]:
    return {
        "paper_execution_authorized": False,
        "live_authorization": False,
        "execution_authorized": False,
        "live_execution": False,
        "financial_execution": False,
        "read_only": True,
    }


@router.get("/health")
async def evidence_incidents_health():
    summary = _journal().summary()

    return {
        "status": "healthy",
        "active_incidents": summary[
            "active_incidents"
        ],
        "total_incidents": summary[
            "total_incidents"
        ],
        "snapshots": summary[
            "snapshots"
        ],
        **_safe_base(),
    }


@router.get("/summary")
async def evidence_incidents_summary():
    return _journal().summary()


@router.get("/active")
async def evidence_incidents_active(
    limit: int = Query(
        default=100,
        ge=1,
        le=5000,
    ),
    severity: str | None = Query(
        default=None
    ),
):
    try:
        incidents = (
            _journal().list_incidents(
                status="ACTIVE",
                severity=severity,
                limit=limit,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "count": len(incidents),
        "incidents": incidents,
        **_safe_base(),
    }


@router.get("/history")
async def evidence_incidents_history(
    limit: int = Query(
        default=250,
        ge=1,
        le=5000,
    ),
    status: str | None = Query(
        default=None
    ),
    severity: str | None = Query(
        default=None
    ),
):
    try:
        incidents = (
            _journal().list_incidents(
                status=status,
                severity=severity,
                limit=limit,
            )
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    return {
        "count": len(incidents),
        "incidents": incidents,
        **_safe_base(),
    }


@router.get("/snapshots")
async def evidence_incidents_snapshots(
    limit: int = Query(
        default=250,
        ge=1,
        le=5000,
    ),
):
    snapshots = (
        _journal().list_snapshots(
            limit=limit
        )
    )

    return {
        "count": len(snapshots),
        "snapshots": snapshots,
        **_safe_base(),
    }


@router.get("/{incident_id}")
async def evidence_incident_detail(
    incident_id: str,
):
    incident = (
        _journal().get_incident(
            incident_id
        )
    )

    if incident is None:
        raise HTTPException(
            status_code=404,
            detail=(
                "Incidente não encontrado."
            ),
        )

    return {
        "incident": incident,
        **_safe_base(),
    }


@router.post("/capture")
async def evidence_incidents_capture(
    confirm: str = Query(...),
):
    if (
        confirm
        != "CAPTURE-PAPER-EVIDENCE-INCIDENTS"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "CAPTURE-PAPER-EVIDENCE-INCIDENTS."
            ),
        )

    snapshot = (
        paper_certification_evidence_monitor
        .snapshot()
    )

    return _journal().capture(
        snapshot
    )


@router.post(
    "/{incident_id}/acknowledge"
)
async def evidence_incident_acknowledge(
    incident_id: str,
    confirm: str = Query(...),
    acknowledged_by: str = Query(
        default="operator",
        max_length=120,
    ),
    note: str | None = Query(
        default=None,
        max_length=1000,
    ),
):
    if (
        confirm
        != "ACK-PAPER-EVIDENCE-INCIDENT"
    ):
        raise HTTPException(
            status_code=400,
            detail=(
                "Confirmação inválida. Use "
                "ACK-PAPER-EVIDENCE-INCIDENT."
            ),
        )

    try:
        return _journal().acknowledge(
            incident_id,
            acknowledged_by=(
                acknowledged_by
            ),
            note=note,
        )

    except KeyError as exc:
        raise HTTPException(
            status_code=404,
            detail=(
                "Incidente não encontrado."
            ),
        ) from exc
