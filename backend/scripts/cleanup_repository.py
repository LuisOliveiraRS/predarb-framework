from __future__ import annotations

import argparse
import shutil
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
APP_DIR = ROOT / "app"


def candidates() -> list[Path]:
    items: list[Path] = []

    for child in APP_DIR.iterdir():
        name = child.name.lower()
        if (
            "backup" in name
            or name.endswith("-bkp")
            or child.suffix.lower() == ".zip"
        ):
            items.append(child)

    for cache in APP_DIR.rglob("__pycache__"):
        items.append(cache)

    for bytecode in APP_DIR.rglob("*.py[co]"):
        items.append(bytecode)

    return sorted(set(items), key=lambda path: (len(path.parts), str(path)))


def main() -> int:
    parser = argparse.ArgumentParser(
        description=(
            "Remove caches e move backups/ZIPs antigos para fora de app/. "
            "Sem --apply, apenas mostra o plano."
        )
    )
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()

    items = candidates()
    archive_root = ROOT / "repository_archive" / datetime.now(
        timezone.utc
    ).strftime("%Y%m%dT%H%M%SZ")

    print(f"Itens encontrados: {len(items)}")

    for item in items:
        relative = item.relative_to(ROOT)

        if item.name == "__pycache__" or item.suffix.lower() in {".pyc", ".pyo"}:
            action = "DELETE"
        else:
            action = "ARCHIVE"

        print(f"{action:7} {relative}")

        if not args.apply:
            continue

        if action == "DELETE":
            if item.is_dir():
                shutil.rmtree(item, ignore_errors=True)
            else:
                item.unlink(missing_ok=True)
            continue

        destination = archive_root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(item), str(destination))

    if args.apply:
        print(f"Arquivo morto movido para: {archive_root}")
    else:
        print("Dry-run concluído. Execute novamente com --apply para aplicar.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
