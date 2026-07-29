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

SERVICE_FILE = (
    BACKEND
    / "app"
    / "real_markets"
    / "service.py"
)

FILES = {
    PAYLOAD
    / "app"
    / "real_markets"
    / "polymarket.py":
        BACKEND
        / "app"
        / "real_markets"
        / "polymarket.py",

    PAYLOAD
    / "app"
    / "api"
    / "routers"
    / "polymarket_read_only.py":
        BACKEND
        / "app"
        / "api"
        / "routers"
        / "polymarket_read_only.py",

    PAYLOAD
    / "tests"
    / "test_polymarket_read_only_connector.py":
        BACKEND
        / "tests"
        / "test_polymarket_read_only_connector.py",
}


ROUTER_IMPORT_LINE = (
    "from app.api.routers."
    "polymarket_read_only "
    "import router as "
    "polymarket_read_only_router"
)

CONNECTOR_IMPORT = (
    "from app.real_markets.polymarket import (\n"
    "    build_polymarket_connector_from_env,\n"
    ")"
)

CONNECTOR_REGISTRATION = (
    "_polymarket_connector = (\n"
    "    build_polymarket_connector_from_env()\n"
    ")\n\n"
    "if _polymarket_connector is not None:\n"
    "    real_market_registry.register(\n"
    "        _polymarket_connector\n"
    "    )"
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


def patch_service(
    backup_dir: Path,
) -> None:
    if not SERVICE_FILE.is_file():
        raise FileNotFoundError(
            SERVICE_FILE
        )

    backup_file(
        SERVICE_FILE,
        backup_dir,
    )

    text = SERVICE_FILE.read_text(
        encoding="utf-8"
    )

    if CONNECTOR_IMPORT not in text:
        lines = text.splitlines()

        inserted = insert_after_import_statement(
            lines,
            anchor=(
                "app.real_markets.connectors"
            ),
            new_line=CONNECTOR_IMPORT,
        )

        if not inserted:
            raise RuntimeError(
                "Import dos conectores da Fase 9A "
                "não foi encontrado."
            )

        text = "\n".join(lines) + "\n"

    if CONNECTOR_REGISTRATION not in text:
        mock_registration = (
            "real_market_registry.register(\n"
            "    MockReadOnlyPredictionConnector()\n"
            ")"
        )

        if mock_registration not in text:
            raise RuntimeError(
                "Registro do conector mock da "
                "Fase 9A não foi encontrado."
            )

        text = text.replace(
            mock_registration,
            (
                mock_registration
                + "\n\n"
                + CONNECTOR_REGISTRATION
            ),
            1,
        )

    SERVICE_FILE.write_text(
        text,
        encoding="utf-8",
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

    if ROUTER_IMPORT_LINE not in text:
        lines = text.splitlines()

        inserted = insert_after_import_statement(
            lines,
            anchor=(
                "real_market_data_router"
            ),
            new_line=ROUTER_IMPORT_LINE,
        )

        if not inserted:
            raise RuntimeError(
                "Import do router da Fase 9A "
                "não foi encontrado."
            )

        text = "\n".join(lines) + "\n"

    entry = (
        "        "
        "polymarket_read_only_router,"
    )

    if entry not in text:
        lines = text.splitlines()
        inserted = False

        for index, line in enumerate(
            lines
        ):
            if (
                line.strip()
                == "real_market_data_router,"
            ):
                lines.insert(
                    index + 1,
                    entry,
                )
                inserted = True
                break

        if not inserted:
            raise RuntimeError(
                "Router da Fase 9A não foi "
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
    from app.real_markets.service import (
        real_market_registry,
    )

    connector = real_market_registry.get(
        "polymarket"
    )

    if connector.read_only is not True:
        raise RuntimeError(
            "O conector Polymarket não está "
            "marcado como somente leitura."
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
        (
            "/real-markets/polymarket/"
            "configuration"
        ),
        (
            "/real-markets/polymarket/"
            "health"
        ),
        (
            "/real-markets/polymarket/"
            "markets"
        ),
        (
            "/real-markets/polymarket/"
            "markets/{market_id}/snapshot"
        ),
        (
            "/real-markets/polymarket/"
            "architecture"
        ),
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

    if not SERVICE_FILE.is_file():
        raise RuntimeError(
            "A Fase 9A precisa estar instalada "
            "antes da Fase 9B."
        )

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = (
        BACKEND
        / "backups"
        / "phase9b"
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

    patch_service(
        backup_dir
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
        str(SERVICE_FILE),
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
        "FASE 9B INSTALADA E VALIDADA"
    )
    print(
        "Backup:",
        backup_dir,
    )
    print()
    print(
        "Conector externo registrado: polymarket"
    )
    print(
        "Modo: dados públicos somente leitura"
    )
    print(
        "Credenciais de negociação: não utilizadas"
    )
    print(
        "Envio ou cancelamento de ordens: indisponível"
    )
    print(
        "Runtime em background: não iniciado"
    )


if __name__ == "__main__":
    main()
