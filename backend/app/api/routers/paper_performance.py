from __future__ import annotations

from fastapi import (
    APIRouter,
    HTTPException,
    Query,
)

from app.paper.performance import (
    PaperPerformanceService,
)


router = APIRouter(
    prefix="/paper/performance",
    tags=["paper-performance"],
)


def _service() -> PaperPerformanceService:
    return PaperPerformanceService()


@router.get("/health")
async def paper_performance_health():
    service = _service()

    return {
        "status": "healthy",
        "reports_dir": str(
            service.reports_dir
        ),
        "execution_authorized": False,
        "live_execution": False,
    }


@router.get("/summary")
async def paper_performance_summary():
    return _service().summary()


@router.get("/reports")
async def paper_performance_reports(
    limit: int = Query(
        default=50,
        ge=1,
        le=500,
    ),
):
    reports = _service().list_reports(
        limit=limit
    )

    return {
        "count": len(reports),
        "reports": reports,
        "execution_authorized": False,
        "live_execution": False,
    }


@router.get("/history")
async def paper_performance_history(
    limit: int = Query(
        default=500,
        ge=1,
        le=5000,
    ),
    report_limit: int = Query(
        default=20,
        ge=1,
        le=200,
    ),
):
    points = _service().history(
        limit=limit,
        report_limit=report_limit,
    )

    return {
        "count": len(points),
        "points": points,
        "execution_authorized": False,
        "live_execution": False,
    }


@router.get("/reports/{report_name}")
async def paper_performance_report(
    report_name: str,
):
    try:
        report = _service().get_report(
            report_name
        )

    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail=str(exc),
        ) from exc

    except FileNotFoundError as exc:
        raise HTTPException(
            status_code=404,
            detail="Relatório não encontrado.",
        ) from exc

    return report
