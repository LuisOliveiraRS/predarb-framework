from __future__ import annotations

import logging
from typing import Any

from app.plugins.loader import PluginLoader
from app.plugins.registry import PluginRegistry, registry


logger = logging.getLogger(__name__)


class PluginManager:
    """Controla descoberta, inicialização e encerramento dos plugins."""

    def __init__(
        self,
        *,
        loader: PluginLoader | None = None,
        plugin_registry: PluginRegistry | None = None,
    ) -> None:
        self.loader = loader or PluginLoader()
        self.registry = plugin_registry or registry
        self._started: set[str] = set()
        self.last_report: dict[str, Any] = {}

    def load(self) -> dict[str, Any]:
        loaded: list[str] = []
        skipped: list[str] = []
        errors: dict[str, str] = {}

        for plugin_info in self.loader.discover():
            name = str(plugin_info["name"])
            try:
                current = self.registry.get(name)
                if current is not None and name in self._started:
                    skipped.append(name)
                    continue

                plugin_class = self.loader.load_class(plugin_info["entrypoint"])
                plugin = plugin_class()
                self.registry.register(plugin)
                plugin.start()
                self._started.add(name)
                loaded.append(name)
            except Exception as exc:
                errors[name] = str(exc)
                logger.exception("Falha ao carregar plugin %s.", name)

        self.last_report = {
            "loaded": loaded,
            "skipped": skipped,
            "errors": errors,
            "registry": self.registry.status(),
            "discovery": dict(self.loader.last_report),
        }
        return dict(self.last_report)

    def stop(self) -> dict[str, Any]:
        stopped: list[str] = []
        errors: dict[str, str] = {}

        for plugin in reversed(self.registry.get_all()):
            name = str(getattr(plugin, "name", plugin.__class__.__name__))
            if name not in self._started:
                continue
            try:
                plugin.stop()
                stopped.append(name)
            except Exception as exc:
                errors[name] = str(exc)
                logger.exception("Falha ao encerrar plugin %s.", name)
            finally:
                self._started.discard(name)

        self.last_report = {
            "stopped": stopped,
            "errors": errors,
            "registry": self.registry.status(),
        }
        return dict(self.last_report)

    def plugins(self) -> list[dict[str, str]]:
        return [
            {
                "name": str(plugin.name),
                "version": str(plugin.version),
            }
            for plugin in self.registry.get_all()
        ]

    def status(self) -> dict[str, Any]:
        return {
            "started": sorted(self._started),
            "registry": self.registry.status(),
            "last_report": dict(self.last_report),
        }


plugin_manager = PluginManager()
