from __future__ import annotations

from pathlib import Path

from fastapi.routing import (
    APIRoute,
    APIWebSocketRoute,
    iter_route_contexts,
)
from starlette.routing import Mount

from app.api.routers.paper import router as paper_router
from app.core.application import create_app
from app.dashboard.router_ws import router as ws_router


def main() -> None:
    print("paper.py:", Path(__import__(
        "app.api.routers.paper",
        fromlist=["__file__"],
    ).__file__).resolve())

    print("router_ws.py:", Path(__import__(
        "app.dashboard.router_ws",
        fromlist=["__file__"],
    ).__file__).resolve())

    local_paper_paths = {
        route.path
        for route in paper_router.routes
        if isinstance(route, APIRoute)
    }

    local_ws_paths = {
        route.path
        for route in ws_router.routes
        if isinstance(route, APIWebSocketRoute)
    }

    required = {
        "/paper/risk/status",
        "/paper/session/status",
        "/paper/session/report",
        "/paper/session/cycle",
        "/paper/session/start",
        "/paper/session/stop",
        "/paper/session/reset-report",
    }

    print("Rotas no paper_router:", len(paper_router.routes))
    print("Rotas no router_ws:", len(ws_router.routes))
    print(
        "Paper ausentes no router local:",
        sorted(required - local_paper_paths),
    )
    print("WebSockets locais:", sorted(local_ws_paths))

    app = create_app()
    contexts = list(iter_route_contexts(app.routes))

    http_paths = {
        context.path
        for context in contexts
        if isinstance(context.original_route, APIRoute)
    }

    ws_paths = {
        context.path
        for context in contexts
        if isinstance(context.original_route, APIWebSocketRoute)
    }

    mount_paths = {
        context.path
        for context in contexts
        if isinstance(context.original_route, Mount)
    }

    missing_app = sorted(required - http_paths)

    print("Rotas HTTP na aplicação:", len(http_paths))
    print("Paper ausentes na aplicação:", missing_app)
    print("WebSockets na aplicação:", sorted(ws_paths))
    print("Mounts:", sorted(mount_paths))

    assert not missing_app, missing_app
    assert "/ws/router" in ws_paths
    assert "/dashboard/static" in mount_paths

    print()
    print("DEFINIÇÕES DE ROTAS DA FASE 7 VALIDADAS")


if __name__ == "__main__":
    main()
