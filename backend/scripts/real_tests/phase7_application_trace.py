from __future__ import annotations

import hashlib
import inspect
from pathlib import Path

from fastapi import FastAPI
from fastapi.routing import APIRoute, APIWebSocketRoute
from starlette.routing import Mount

import app.core.application as application
from app.api.routers.paper import router as direct_paper_router
from app.dashboard.router_ws import router as direct_ws_router


application_path = Path(application.__file__).resolve()
source_bytes = application_path.read_bytes()
source_text = source_bytes.decode("utf-8")


print("=" * 70)
print("ARQUIVO E CÓDIGO CARREGADO")
print("=" * 70)

print("Arquivo:", application_path)
print(
    "SHA256:",
    hashlib.sha256(source_bytes).hexdigest().upper(),
)
print(
    "Linha da função:",
    application.create_app.__code__.co_firstlineno,
)
print(
    "include_router no arquivo:",
    "include_router" in source_text,
)


function_source = inspect.getsource(
    application.create_app
)

print(
    "include_router na função carregada:",
    "include_router" in function_source,
)

print(
    "paper_router na função carregada:",
    "paper_router" in function_source,
)

print(
    "ai_dashboard_ws_router na função carregada:",
    "ai_dashboard_ws_router" in function_source,
)


print()
print("=" * 70)
print("IDENTIDADE DOS ROUTERS")
print("=" * 70)


application_paper = getattr(
    application,
    "paper_router",
    None,
)

application_ws = getattr(
    application,
    "ai_dashboard_ws_router",
    None,
)


print(
    "Paper direto:",
    id(direct_paper_router),
    len(direct_paper_router.routes),
)

print(
    "Paper no application:",
    id(application_paper),
    len(application_paper.routes)
    if application_paper is not None
    else None,
)

print(
    "Mesmo Paper:",
    application_paper is direct_paper_router,
)


print(
    "WS direto:",
    id(direct_ws_router),
    len(direct_ws_router.routes),
)

print(
    "WS no application:",
    id(application_ws),
    len(application_ws.routes)
    if application_ws is not None
    else None,
)

print(
    "Mesmo WS:",
    application_ws is direct_ws_router,
)


print()
print("=" * 70)
print("RASTREAMENTO DO include_router")
print("=" * 70)


original_include_router = FastAPI.include_router
calls = []


def traced_include_router(
    self,
    router,
    *args,
    **kwargs,
):
    entry = {
        "id": id(router),
        "prefix": getattr(
            router,
            "prefix",
            None,
        ),
        "routes": len(
            getattr(
                router,
                "routes",
                [],
            )
        ),
    }

    calls.append(entry)

    print(
        "include_router:",
        entry,
    )

    return original_include_router(
        self,
        router,
        *args,
        **kwargs,
    )


FastAPI.include_router = traced_include_router


try:
    app = application.create_app()

finally:
    FastAPI.include_router = original_include_router


print()
print("Chamadas ao include_router:", len(calls))


http_paths = [
    route.path
    for route in app.routes
    if isinstance(route, APIRoute)
]

ws_paths = [
    route.path
    for route in app.routes
    if isinstance(route, APIWebSocketRoute)
]

mount_paths = [
    route.path
    for route in app.routes
    if isinstance(route, Mount)
]


print("Rotas HTTP:", len(http_paths))
print("WebSockets:", ws_paths)
print("Mounts:", mount_paths)
print("Paper presente:", "/paper/risk/status" in http_paths)
print("WS presente:", "/ws/router" in ws_paths)


print()
print("=" * 70)
print("FINAL DA FUNÇÃO CARREGADA")
print("=" * 70)

lines = function_source.splitlines()

for line in lines[-35:]:
    print(line)
