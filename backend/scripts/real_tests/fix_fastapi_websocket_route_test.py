from __future__ import annotations

import ast
from datetime import datetime
from pathlib import Path


BACKEND = Path.cwd().resolve()
TEST_FILE = BACKEND / "tests" / "test_application_integration.py"


REPLACEMENT = '''def test_application_has_no_duplicate_routes():
    from fastapi.routing import (
        APIRoute,
        APIWebSocketRoute,
        iter_route_contexts,
    )
    from starlette.routing import Mount

    def effective_path(context):
        path = context.path
        if path:
            return path

        effective_route = getattr(
            context,
            "_effective_route",
            None,
        )

        starlette_route = getattr(
            effective_route,
            "starlette_route",
            None,
        )

        starlette_path = getattr(
            starlette_route,
            "path",
            None,
        )

        if starlette_path:
            return starlette_path

        return getattr(
            context.original_route,
            "path",
            "",
        )

    app = application.create_app()
    seen = set()

    for context in iter_route_contexts(app.routes):
        original_route = context.original_route
        path = effective_path(context)

        if isinstance(original_route, APIRoute):
            key = (
                path,
                tuple(sorted(context.methods or ())),
            )
        elif isinstance(original_route, APIWebSocketRoute):
            key = (
                path,
                ("WEBSOCKET",),
            )
        elif isinstance(original_route, Mount):
            key = (
                path,
                ("MOUNT",),
            )
        else:
            continue

        assert key not in seen, key
        seen.add(key)

    assert ("/dashboard/static", ("MOUNT",)) in seen
    assert ("/ws/router", ("WEBSOCKET",)) in seen
'''


def replace_function(
    path: Path,
    function_name: str,
    replacement: str,
) -> None:
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)

    target = None

    for node in tree.body:
        if isinstance(
            node,
            (ast.FunctionDef, ast.AsyncFunctionDef),
        ) and node.name == function_name:
            target = node
            break

    if target is None:
        raise RuntimeError(
            f"Função {function_name!r} não encontrada em {path}."
        )

    lines = source.splitlines(keepends=True)
    start = target.lineno - 1
    end = target.end_lineno

    updated = (
        "".join(lines[:start])
        + replacement.rstrip()
        + "\n\n"
        + "".join(lines[end:])
    )

    path.write_text(
        updated,
        encoding="utf-8",
    )


def main() -> None:
    if BACKEND.name.lower() != "backend":
        raise RuntimeError(
            "Execute este instalador dentro de "
            "C:\\predarb-framework\\backend."
        )

    if not TEST_FILE.is_file():
        raise FileNotFoundError(TEST_FILE)

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup = TEST_FILE.with_name(
        f"{TEST_FILE.stem}_before_ws_context_fix_"
        f"{stamp}{TEST_FILE.suffix}"
    )

    backup.write_bytes(
        TEST_FILE.read_bytes()
    )

    replace_function(
        TEST_FILE,
        "test_application_has_no_duplicate_routes",
        REPLACEMENT,
    )

    print("Teste de rotas WebSocket corrigido.")
    print("Arquivo:", TEST_FILE)
    print("Backup:", backup)


if __name__ == "__main__":
    main()
