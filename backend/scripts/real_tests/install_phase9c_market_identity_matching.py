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

PHASE9A_SERVICE = (
    BACKEND
    / "app"
    / "real_markets"
    / "service.py"
)

PHASE9B_CONNECTOR = (
    BACKEND
    / "app"
    / "real_markets"
    / "polymarket.py"
)

FILES = {
    PAYLOAD
    / "app"
    / "real_markets"
    / "matching.py":
        BACKEND
        / "app"
        / "real_markets"
        / "matching.py",

    PAYLOAD
    / "app"
    / "api"
    / "routers"
    / "market_matching.py":
        BACKEND
        / "app"
        / "api"
        / "routers"
        / "market_matching.py",

    PAYLOAD
    / "tests"
    / "test_market_identity_matching.py":
        BACKEND
        / "tests"
        / "test_market_identity_matching.py",
}


IMPORT_LINE = (
    "from app.api.routers."
    "market_matching "
    "import router as "
    "market_matching_router"
)


def backup_file(
    source: Path,
    backup_dir: Path,
) -> None:
    if source.is_file():
        relative_name = (
            str(
                source.relative_to(
                    BACKEND
                )
            )
            .replace("\\", "__")
            .replace("/", "__")
        )

        shutil.copy2(
            source,
            backup_dir
            / f"{relative_name}.bak",
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

        inserted = insert_after_import_statement(
            lines,
            anchor=(
                "polymarket_read_only_router"
            ),
            new_line=IMPORT_LINE,
        )

        if not inserted:
            raise RuntimeError(
                "Import do router da Fase 9B "
                "não foi encontrado."
            )

        text = "\n".join(lines) + "\n"

    entry = (
        "        "
        "market_matching_router,"
    )

    if entry not in text:
        lines = text.splitlines()
        inserted = False

        for index, line in enumerate(
            lines
        ):
            if (
                line.strip()
                == (
                    "polymarket_read_only_router,"
                )
            ):
                lines.insert(
                    index + 1,
                    entry,
                )
                inserted = True
                break

        if not inserted:
            raise RuntimeError(
                "Router da Fase 9B não foi "
                "encontrado na coleção de routers."
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


def validate_installation() -> None:
    from fastapi.routing import (
        APIRoute,
        iter_route_contexts,
    )

    from app.core.application import (
        create_app,
    )
    from app.real_markets.matching import (
        market_matching_service,
    )

    health = (
        market_matching_service
        .health()
    )

    if (
        health[
            "automatic_matching_authorized"
        ]
        is not False
    ):
        raise RuntimeError(
            "Correspondência automática "
            "não está bloqueada."
        )

    if (
        health["live_execution"]
        is not False
        or health[
            "financial_execution"
        ]
        is not False
    ):
        raise RuntimeError(
            "Guardas de execução inválidas."
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
        "/real-markets/matching/health",
        "/real-markets/matching/identities",
        "/real-markets/matching/compare",
        "/real-markets/matching/candidates",
        "/real-markets/matching/manual-matches",
        (
            "/real-markets/matching/"
            "manual-matches/{match_id}"
        ),
        "/real-markets/matching/dashboard",
        "/real-markets/matching/architecture",
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

    if not PHASE9A_SERVICE.is_file():
        raise RuntimeError(
            "A Fase 9A precisa estar instalada."
        )

    if not PHASE9B_CONNECTOR.is_file():
        raise RuntimeError(
            "A Fase 9B precisa estar instalada."
        )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = (
        BACKEND
        / "backups"
        / "phase9c"
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
    validate_installation()

    print()
    print(
        "FASE 9C INSTALADA E VALIDADA"
    )
    print(
        "Backup:",
        backup_dir,
    )
    print()
    print(
        "Fingerprint e similaridade: habilitados"
    )
    print(
        "Correspondência automática: bloqueada"
    )
    print(
        "Confirmação manual: obrigatória"
    )
    print(
        "Execução real e financeira: bloqueadas"
    )


if __name__ == "__main__":
    main()
