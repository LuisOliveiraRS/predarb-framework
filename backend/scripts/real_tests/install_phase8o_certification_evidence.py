from __future__ import annotations

import py_compile
import shutil
import sys
from datetime import datetime
from pathlib import Path


BACKEND = Path.cwd().resolve()

if str(BACKEND) not in sys.path:
    sys.path.insert(
        0,
        str(BACKEND),
    )

PACKAGE_ROOT = (
    Path(__file__).resolve().parents[2]
)
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
    / "certification_evidence.py":
        BACKEND
        / "app"
        / "paper"
        / "certification_evidence.py",

    PAYLOAD
    / "app"
    / "api"
    / "routers"
    / "paper_certification_evidence.py":
        BACKEND
        / "app"
        / "api"
        / "routers"
        / "paper_certification_evidence.py",

    PAYLOAD
    / "tests"
    / "test_paper_certification_evidence.py":
        BACKEND
        / "tests"
        / "test_paper_certification_evidence.py",
}


IMPORT_LINE = (
    "from app.api.routers."
    "paper_certification_evidence "
    "import router as "
    "paper_certification_evidence_router"
)


def backup_file(
    source: Path,
    backup_dir: Path,
) -> None:
    if not source.is_file():
        return

    shutil.copy2(
        source,
        backup_dir
        / f"{source.name}.bak",
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
        lines = text.splitlines()
        inserted = False

        for index, line in enumerate(lines):
            if (
                line.startswith("from ")
                and "paper_stability_certification_router"
                in line
            ):
                lines.insert(
                    index + 1,
                    IMPORT_LINE,
                )
                inserted = True
                break

        if not inserted:
            raise RuntimeError(
                "Import da Fase 8N "
                "não encontrado."
            )

        text = "\n".join(lines) + "\n"

    entry = (
        "        "
        "paper_certification_evidence_router,"
    )

    if entry not in text:
        lines = text.splitlines()
        inserted = False

        for index, line in enumerate(lines):
            if (
                line.strip()
                == "paper_stability_certification_router,"
            ):
                lines.insert(
                    index + 1,
                    entry,
                )
                inserted = True
                break

        if not inserted:
            raise RuntimeError(
                "Router da Fase 8N não "
                "encontrado na tupla."
            )

        text = "\n".join(lines) + "\n"

    APPLICATION_FILE.write_text(
        text,
        encoding="utf-8",
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
        "/paper/certification/evidence/health",
        "/paper/certification/evidence/summary",
        "/paper/certification/evidence/verify",
        "/paper/certification/evidence/latest",
        "/paper/certification/evidence/entries",
        "/paper/certification/evidence/snapshot",
        "/paper/certification/evidence/capture",
        "/paper/certification/evidence/dashboard",
        "/paper/certification/evidence/export.csv",
        "/paper/certification/evidence/export.json",
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


def main() -> None:
    if BACKEND.name.lower() != "backend":
        raise RuntimeError(
            "Execute dentro de "
            "C:\\predarb-framework\\backend."
        )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = (
        BACKEND
        / "backups"
        / "phase8o"
        / stamp
    )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    for source, destination in FILES.items():
        if not source.is_file():
            raise FileNotFoundError(
                source
            )

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

    for destination in FILES.values():
        py_compile.compile(
            str(destination),
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
        "FASE 8O INSTALADA E VALIDADA"
    )
    print(
        "Backup:",
        backup_dir,
    )


if __name__ == "__main__":
    main()
