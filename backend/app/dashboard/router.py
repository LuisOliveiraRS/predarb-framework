from __future__ import annotations

from app.core.settings import settings

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


@router.get("/login", include_in_schema=False)
async def login_page(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "request": request,
            "app_name": settings.APP_NAME,
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response


@router.get(
    "/esqueci-senha",
    include_in_schema=False,
    name="forgot_password_page",
)
async def forgot_password_page(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="forgot_password.html",
        context={
            "request": request,
            "app_name": settings.APP_NAME,
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response


@router.get(
    "/redefinir-senha",
    include_in_schema=False,
    name="password_reset_page",
)
async def password_reset_page(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="reset_password.html",
        context={
            "request": request,
            "app_name": settings.APP_NAME,
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response

@router.get(
    "/mfa",
    include_in_schema=False,
    name="mfa_page",
)
async def mfa_page(request: Request):
    response = templates.TemplateResponse(
        request=request,
        name="mfa.html",
        context={
            "request": request,
            "app_name": settings.APP_NAME,
        },
    )

    response.headers["Cache-Control"] = "no-store"
    return response
