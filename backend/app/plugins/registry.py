from __future__ import annotations

from threading import RLock

from app.plugins.base import BasePlugin


class PluginRegistry:
    def __init__(self) -> None:
        self._plugins: dict[str, BasePlugin] = {}
        self._lock = RLock()

    def register(self, plugin: BasePlugin, *, replace: bool = True) -> BasePlugin:
        name = str(getattr(plugin, "name", "") or "").strip()
        if not name:
            raise ValueError("O plugin deve possuir um nome válido.")

        with self._lock:
            current = self._plugins.get(name)
            if current is not None and current is not plugin and not replace:
                raise KeyError(f"Plugin já registrado: {name}")
            self._plugins[name] = plugin
        return plugin

    def unregister(self, name: str) -> BasePlugin | None:
        with self._lock:
            return self._plugins.pop(str(name).strip(), None)

    def get_all(self) -> list[BasePlugin]:
        with self._lock:
            return list(self._plugins.values())

    def get(self, name: str) -> BasePlugin | None:
        with self._lock:
            return self._plugins.get(str(name).strip())

    def clear(self) -> int:
        with self._lock:
            count = len(self._plugins)
            self._plugins.clear()
            return count

    def status(self) -> dict[str, object]:
        with self._lock:
            return {
                "plugins": len(self._plugins),
                "names": sorted(self._plugins),
            }


registry = PluginRegistry()
