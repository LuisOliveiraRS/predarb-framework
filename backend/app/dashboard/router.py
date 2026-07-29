from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from fastapi.responses import RedirectResponse
from fastapi.templating import Jinja2Templates


BASE_DIR = Path(__file__).resolve().parent
TEMPLATES_DIR = BASE_DIR / "templates"


templates = Jinja2Templates(
    directory=str(TEMPLATES_DIR),
)

router = APIRouter(
    tags=["Dashboard"],
)


def _dashboard_response(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "title": "PredArb Enterprise Dashboard",
            "api_base": "/dashboard/api",
            "router_ws_path": "/ws/router",
        },
    )
    response.headers["Cache-Control"] = "no-store, max-age=0"
    return response


@router.get("/dashboard", include_in_schema=False)
async def dashboard_page(request: Request):
    return _dashboard_response(request)


@router.get("/dashboard/", include_in_schema=False)
async def dashboard_page_slash(request: Request):
    return _dashboard_response(request)


@router.get("/dashboard/index", include_in_schema=False)
async def dashboard_index_redirect() -> RedirectResponse:
    return RedirectResponse(
        url="/dashboard",
        status_code=307,
    )
