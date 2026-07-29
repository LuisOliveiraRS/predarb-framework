from __future__ import annotations

import importlib
from pathlib import Path
from typing import Any

import yaml


class PluginLoader:
    """Descobre plugins a partir de manifests YAML localizados no pacote."""

    REQUIRED_FIELDS = ("name", "version", "entrypoint")

    def __init__(self, base_path: str | Path | None = None) -> None:
        self.base_path = (
            Path(base_path).expanduser().resolve()
            if base_path is not None
            else Path(__file__).resolve().parent / "installed"
        )
        self.last_report: dict[str, Any] = {}

    def discover(self) -> list[dict[str, Any]]:
        plugins: list[dict[str, Any]] = []
        errors: dict[str, str] = {}

        if not self.base_path.is_dir():
            self.last_report = {
                "base_path": str(self.base_path),
                "discovered": 0,
                "errors": {},
            }
            return plugins

        for folder in sorted(self.base_path.iterdir(), key=lambda item: item.name):
            if not folder.is_dir():
                continue

            manifest = folder / "plugin.yaml"
            if not manifest.is_file():
                continue

            try:
                data = yaml.safe_load(manifest.read_text(encoding="utf-8"))
                if not isinstance(data, dict):
                    raise ValueError("O manifest deve conter um objeto YAML.")

                missing = [field for field in self.REQUIRED_FIELDS if not data.get(field)]
                if missing:
                    raise ValueError(
                        "Campos obrigatórios ausentes: " + ", ".join(missing)
                    )

                normalized = dict(data)
                normalized["name"] = str(normalized["name"]).strip()
                normalized["version"] = str(normalized["version"]).strip()
                normalized["entrypoint"] = str(normalized["entrypoint"]).strip()
                normalized["manifest_path"] = str(manifest)
                plugins.append(normalized)
            except Exception as exc:
                errors[folder.name] = str(exc)

        self.last_report = {
            "base_path": str(self.base_path),
            "discovered": len(plugins),
            "errors": errors,
        }
        return plugins

    def load_class(self, entrypoint: str):
        normalized = str(entrypoint or "").strip()
        parts = normalized.split(".")

        if len(parts) < 2 or any(not part for part in parts):
            raise ValueError(
                "EntryPoint inválido. Use o formato pasta.arquivo.Classe."
            )

        class_name = parts[-1]
        module_path = ".".join(parts[:-1])
        module = importlib.import_module(
            f"app.plugins.installed.{module_path}"
        )
        plugin_class = getattr(module, class_name)

        if not callable(plugin_class):
            raise TypeError("O entrypoint do plugin não é instanciável.")

        return plugin_class
