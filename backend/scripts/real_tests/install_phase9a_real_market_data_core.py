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
    / "real_markets"
    / "__init__.py":
        BACKEND
        / "app"
        / "real_markets"
        / "__init__.py",

    PAYLOAD
    / "app"
    / "real_markets"
    / "models.py":
        BACKEND
        / "app"
        / "real_markets"
        / "models.py",

    PAYLOAD
    / "app"
    / "real_markets"
    / "connectors.py":
        BACKEND
        / "app"
        / "real_markets"
        / "connectors.py",

    PAYLOAD
    / "app"
    / "real_markets"
    / "registry.py":
        BACKEND
        / "app"
        / "real_markets"
        / "registry.py",

    PAYLOAD
    / "app"
    / "real_markets"
    / "service.py":
        BACKEND
        / "app"
        / "real_markets"
        / "service.py",

    PAYLOAD
    / "app"
    / "api"
    / "routers"
    / "real_market_data.py":
        BACKEND
        / "app"
        / "api"
        / "routers"
        / "real_market_data.py",

    PAYLOAD
    / "tests"
    / "test_real_market_data_core.py":
        BACKEND
        / "tests"
        / "test_real_market_data_core.py",
}


IMPORT_LINE = (
    "from app.api.routers."
    "real_market_data "
    "import router as "
    "real_market_data_router"
)


def backup_file(
    source: Path,
    backup_dir: Path,
) -> None:
    if source.is_file():
        shutil.copy2(
            source,
            backup_dir
            / f"{source.name}.bak",
        )


def insert_after_import_statement(
    lines: list[str],
    *,
    anchor: str,
    new_line: str,
) -> bool:
    for index, line in enumerate(
        lines
    ):
        if anchor not in line:
            continue

        end_index = index

        if (
            "(" in line
            and ")" not in line
        ):
            for candidate in range(
                index + 1,
                len(lines),
            ):
                end_index = candidate

                if ")" in lines[
                    candidate
                ]:
                    break

        lines.insert(
            end_index + 1,
            new_line,
        )

        return True

    return False


def insert_after_router_entry(
    lines: list[str],
    *,
    anchor: str,
    new_line: str,
) -> bool:
    for index, line in enumerate(
        lines
    ):
        if line.strip() == anchor:
            lines.insert(
                index + 1,
                new_line,
            )
            return True

    router_indexes = [
        index
        for index, line in enumerate(
            lines
        )
        if (
            line.startswith("        ")
            and line.strip().endswith(
                "_router,"
            )
        )
    ]

    if not router_indexes:
        return False

    lines.insert(
        router_indexes[-1] + 1,
        new_line,
    )

    return True


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

        inserted = (
            insert_after_import_statement(
                lines,
                anchor=(
                    "paper_final_qualification_"
                    "certification_history_router"
                ),
                new_line=IMPORT_LINE,
            )
        )

        if not inserted:
            raise RuntimeError(
                "Import da Fase 8AV não encontrado."
            )

        text = "\n".join(lines) + "\n"

    entry = (
        "        "
        "real_market_data_router,"
    )

    if entry not in text:
        lines = text.splitlines()

        inserted = insert_after_router_entry(
            lines,
            anchor=(
                "paper_final_qualification_"
                "certification_history_router,"
            ),
            new_line=entry,
        )

        if not inserted:
            raise RuntimeError(
                "Não foi possível localizar "
                "a coleção de routers."
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
        for context in (
            iter_route_contexts(
                app.routes
            )
        )
        if isinstance(
            context.original_route,
            APIRoute,
        )
    }

    required = {
        "/real-markets/health",
        "/real-markets/connectors",
        "/real-markets/markets",
        (
            "/real-markets/markets/"
            "{connector_id}/{market_id}"
        ),
        "/real-markets/snapshots/latest",
        "/real-markets/refresh",
        "/real-markets/dashboard",
        "/real-markets/architecture",
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
        / "phase9a"
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
        "FASE 9A INSTALADA E VALIDADA"
    )
    print(
        "Backup:",
        backup_dir,
    )
    print()
    print(
        "Nenhum conector externo foi ativado."
    )
    print(
        "Execução real e financeira permanecem bloqueadas."
    )


if __name__ == "__main__":
    main()
