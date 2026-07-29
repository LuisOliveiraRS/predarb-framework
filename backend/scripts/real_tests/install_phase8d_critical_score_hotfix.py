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
SOURCE = (
    PACKAGE_ROOT
    / "payload"
    / "app"
    / "paper"
    / "performance_monitor.py"
)
DESTINATION = (
    BACKEND
    / "app"
    / "paper"
    / "performance_monitor.py"
)


def clear_caches() -> None:
    for root in (
        BACKEND / "app",
        BACKEND / "tests",
    ):
        if not root.exists():
            continue

        for cache in root.rglob("__pycache__"):
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

    if not SOURCE.is_file():
        raise FileNotFoundError(SOURCE)

    if not DESTINATION.is_file():
        raise FileNotFoundError(DESTINATION)

    stamp = datetime.now().strftime(
        "%Y%m%d-%H%M%S"
    )

    backup_dir = (
        BACKEND
        / "backups"
        / "phase8d-critical-score"
        / stamp
    )

    backup_dir.mkdir(
        parents=True,
        exist_ok=True,
    )

    backup = (
        backup_dir
        / "performance_monitor.py.bak"
    )

    shutil.copy2(
        DESTINATION,
        backup,
    )

    shutil.copy2(
        SOURCE,
        DESTINATION,
    )

    py_compile.compile(
        str(DESTINATION),
        doraise=True,
    )

    clear_caches()

    from app.paper.performance_monitor import (
        PaperPerformanceMonitor,
        PerformanceAlert,
    )

    score = PaperPerformanceMonitor._score(
        {
            "total_reports": 1,
        },
        {
            "success_cycle_rate": 0.90,
        },
        [
            PerformanceAlert(
                code="SAFETY_VIOLATION",
                severity="critical",
                title="Teste",
                message="Teste",
            )
        ],
    )

    print(
        "Score crítico validado:",
        score,
    )

    if score >= 75:
        raise RuntimeError(
            "O score crítico continua fora "
            "da faixa esperada."
        )

    print()
    print(
        "HOTFIX DA FASE 8D INSTALADO E VALIDADO"
    )
    print(
        "Backup:",
        backup,
    )


if __name__ == "__main__":
    main()
