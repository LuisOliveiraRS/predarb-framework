from __future__ import annotations

import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path


BACKEND = Path.cwd().resolve()

if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
PAYLOAD = PACKAGE_ROOT / "payload"

APPLICATION_FILE = (
    BACKEND
    / "app"
    / "core"
    / "application.py"
)

FILES = {
    PAYLOAD
    / "app"
    / "paper"
    / "performance.py":
        BACKEND
        / "app"
        / "paper"
        / "performance.py",

    PAYLOAD
    / "app"
    / "api"
    / "routers"
    / "paper_performance.py":
        BACKEND
        / "app"
        / "api"
        / "routers"
        / "paper_performance.py",

    PAYLOAD
    / "tests"
    / "test_paper_performance.py":
        BACKEND
        / "tests"
        / "test_paper_performance.py",
}


IMPORT_LINE = (
    "from app.api.routers.paper_performance "
    "import router as paper_performance_router"
)


def backup_file(
    source: Path,
    backup_dir: Path,
) -> None:
    if not source.is_file():
        return

    destination = (
        backup_dir
        / f"{source.name}.bak"
    )

    shutil.copy2(
        source,
        destination,
    )


def patch_application(
    backup_dir: Path,
) -> None:
    if not APPLICATION_FILE.is_file():
        raise FileNotFoundError(
            APPLICATION_FILE
        )

    backup_file(
        APPLICATION_FILE,
        backup_dir,
    )

    text = APPLICATION_FILE.read_text(
        encoding="utf-8"
    )

    if IMPORT_LINE not in text:
        anchor = (
            "from app.api.routers.paper "
            "import router as paper_router"
        )

        if anchor not in text:
            raise RuntimeError(
                "Import de paper_router não "
                "encontrado em application.py."
            )

        text = text.replace(
            anchor,
            anchor + "\n" + IMPORT_LINE,
            1,
        )

    router_entry = "        paper_performance_router,"

    if router_entry not in text:
        anchor = "        paper_router,"

        if anchor not in text:
            raise RuntimeError(
                "paper_router não encontrado "
                "na tupla de routers."
            )

        text = text.replace(
            anchor,
            anchor + "\n" + router_entry,
            1,
        )

    APPLICATION_FILE.write_text(
        text,
        encoding="utf-8",
    )


def validate_routes() -> None:
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.core.application import (
        create_app,
    )

    app = create_app()

    paths = {
        context.path
        for context in iter_route_contexts(
            app.routes
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/paper/performance/health",
        "/paper/performance/summary",
        "/paper/performance/reports",
        "/paper/performance/history",
        "/paper/performance/reports/{report_name}",
    }

    missing = sorted(
        required - paths
    )

    print(
        "Rotas ausentes:",
        missing,
    )

    if missing:
        raise RuntimeError(
            f"Rotas ausentes: {missing}"
        )


def clear_caches() -> None:
    for root in (
        BACKEND / "app",
        BACKEND / "tests",
    ):
        if not root.exists():
            continue

        for cache in root.rglob(
            "__pycache__"
        ):
            shutil.rmtree(
                cache,
                ignore_errors=True,
            )

    shutil.rmtree(
        BACKEND / ".pytest_cache",
        ignore_errors=True,
    )


def main() -> None:
    if BACKEND.name.lower() != "backend":
        raise RuntimeError(
            "Execute dentro de "
            "C:\\predarb-framework\\backend."
        )

    if not PAYLOAD.is_dir():
        raise FileNotFoundError(
            PAYLOAD
        )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = (
        BACKEND
        / "backups"
        / "phase8b"
        / stamp
    )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source, destination in FILES.items():
        if not source.is_file():
            raise FileNotFoundError(source)

        backup_file(
            destination,
            backup_dir,
        )

        destination.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        shutil.copy2(
            source,
            destination,
        )

        print(
            "Instalado:",
            destination,
        )

    patch_application(
        backup_dir
    )

    for file in (
        FILES.values()
    ):
        py_compile.compile(
            str(file),
            doraise=True,
        )

    py_compile.compile(
        str(APPLICATION_FILE),
        doraise=True,
    )

    clear_caches()
    validate_routes()

    print()
    print(
        "FASE 8B INSTALADA E VALIDADA"
    )
    print(
        "Backup:",
        backup_dir,
    )


if __name__ == "__main__":
    main()
