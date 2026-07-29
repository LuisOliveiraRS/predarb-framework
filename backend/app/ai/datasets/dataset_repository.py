from __future__ import annotations

import re
from pathlib import Path
from typing import Any


class DatasetRepository:
    """Resolve caminhos de datasets sem permitir path traversal."""

    NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*$")

    def __init__(self, base: str | Path = "datasets") -> None:
        self.base = Path(base).expanduser().resolve()

    @classmethod
    def normalize_name(cls, name: Any) -> str:
        normalized = str(name or "").strip()
        if normalized.lower().endswith(".csv"):
            normalized = normalized[:-4]

        if not normalized or not cls.NAME_PATTERN.fullmatch(normalized):
            raise ValueError(
                "Nome de dataset inválido. Use apenas letras, números, "
                "ponto, hífen e sublinhado."
            )

        return normalized

    def ensure(self) -> Path:
        self.base.mkdir(parents=True, exist_ok=True)
        return self.base

    def path(self, name: Any, *, create_parent: bool = False) -> Path:
        normalized = self.normalize_name(name)
        if create_parent:
            self.ensure()
        return self.base / f"{normalized}.csv"

    def exists(self, name: Any) -> bool:
        return self.path(name).is_file()

    def list(self) -> list[str]:
        if not self.base.exists():
            return []
        return sorted(path.stem for path in self.base.glob("*.csv") if path.is_file())

    all = list

    def remove(self, name: Any, *, missing_ok: bool = True) -> bool:
        path = self.path(name)
        if not path.exists():
            if missing_ok:
                return False
            raise FileNotFoundError(path)
        path.unlink()
        return True

    def status(self) -> dict[str, Any]:
        datasets = self.list()
        return {
            "base": str(self.base),
            "exists": self.base.exists(),
            "datasets": datasets,
            "count": len(datasets),
        }



dataset_repository = DatasetRepository()
