from __future__ import annotations

from typing import Any

from app.connectors.manager.connector_manager import (
    ConnectorManager,
    connector_manager,
)


class ConnectorRegistry:
    """
    Fachada compatível para o ConnectorManager oficial.

    Este registro não mantém uma segunda coleção
    e não cria conectores automaticamente.

    O bootstrap da aplicação é o único responsável
    por registrar as instâncias oficiais.
    """

    def __init__(
        self,
        manager: ConnectorManager | None = None,
    ) -> None:
        self._manager = (
            manager
            or connector_manager
        )

    def register(
        self,
        name: str,
        connector: Any,
        *,
        replace: bool = True,
    ) -> Any:
        return self._manager.register(
            name,
            connector,
            replace=replace,
        )

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        return self._manager.get(
            name,
            default,
        )

    def require(
        self,
        name: str,
    ) -> Any:
        return self._manager.require(
            name
        )

    def exists(
        self,
        name: str,
    ) -> bool:
        return self._manager.exists(
            name
        )

    def unregister(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        return self._manager.unregister(
            name,
            default,
        )

    def list(
        self,
    ) -> list[str]:
        """
        Preserva o método público original.
        """

        return self._manager.names()

    def names(
        self,
    ) -> list[str]:
        return self._manager.names()

    def all(
        self,
    ) -> dict[str, Any]:
        return self._manager.all()

    def clear(
        self,
    ) -> None:
        self._manager.clear()


registry = ConnectorRegistry()