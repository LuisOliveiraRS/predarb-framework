from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path


BACKEND = Path(r"C:\predarb-framework\backend")
TEST_APPLICATION = BACKEND / "tests" / "test_application_integration.py"
TEST_PAPER = BACKEND / "tests" / "test_paper_risk_session.py"
CHECK_SCRIPT = BACKEND / "scripts" / "real_tests" / "phase7_router_definitions_check.py"


APPLICATION_TEST = '''def test_application_has_no_duplicate_routes():
    from fastapi.routing import (
        APIRoute,
        APIWebSocketRoute,
        iter_route_contexts,
    )
    from starlette.routing import Mount

    app = application.create_app()
    seen = set()

    for context in iter_route_contexts(app.routes):
        original_route = context.original_route

        if isinstance(original_route, APIRoute):
            key = (
                context.path,
                tuple(sorted(context.methods or ())),
            )
        elif isinstance(original_route, APIWebSocketRoute):
            key = (
                context.path,
                ("WEBSOCKET",),
            )
        elif isinstance(original_route, Mount):
            key = (
                context.path,
                ("MOUNT",),
            )
        else:
            continue

        assert key not in seen
        seen.add(key)

    assert ("/dashboard/static", ("MOUNT",)) in seen
    assert ("/ws/router", ("WEBSOCKET",)) in seen
'''


PAPER_TEST = '''def test_paper_session_routes_are_registered():
    from fastapi.routing import APIRoute, iter_route_contexts

    from app.core.application import create_app

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    }

    for path in (
        "/paper/risk/status",
        "/paper/session/status",
        "/paper/session/report",
        "/paper/session/cycle",
        "/paper/session/start",
        "/paper/session/stop",
        "/paper/session/reset-report",
    ):
        assert path in paths
'''


CHECK_SCRIPT_CONTENT = r'''from __future__ import annotations

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
'''


def replace_function(path: Path, function_name: str, replacement: str) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    target = None
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == function_name:
                target = node
                break

    if target is None:
        raise RuntimeError(
            f"Função {function_name!r} não encontrada em {path}."
        )

    lines = source.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno

    replacement_text = replacement.rstrip() + "\n\n"
    updated = "".join(lines[:start]) + replacement_text + "".join(lines[end:])
    path.write_text(updated, encoding="utf-8")


def backup(path: Path, stamp: str) -> Path:
    backup_path = path.with_name(
        f"{path.stem}_before_fastapi_0137_{stamp}{path.suffix}"
    )
    backup_path.write_bytes(path.read_bytes())
    return backup_path


def main() -> None:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")

    for required_path in (TEST_APPLICATION, TEST_PAPER):
        if not required_path.is_file():
            raise FileNotFoundError(required_path)

    backup_application = backup(TEST_APPLICATION, stamp)
    backup_paper = backup(TEST_PAPER, stamp)

    replace_function(
        TEST_APPLICATION,
        "test_application_has_no_duplicate_routes",
        APPLICATION_TEST,
    )

    replace_function(
        TEST_PAPER,
        "test_paper_session_routes_are_registered",
        PAPER_TEST,
    )

    CHECK_SCRIPT.parent.mkdir(parents=True, exist_ok=True)
    if CHECK_SCRIPT.is_file():
        backup(CHECK_SCRIPT, stamp)
    CHECK_SCRIPT.write_text(CHECK_SCRIPT_CONTENT, encoding="utf-8")

    print("Testes atualizados para FastAPI 0.137+.")
    print("Backup:", backup_application)
    print("Backup:", backup_paper)
    print("Diagnóstico:", CHECK_SCRIPT)


if __name__ == "__main__":
    main()
