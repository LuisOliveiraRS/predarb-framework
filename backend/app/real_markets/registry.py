from __future__ import annotations

import threading
from typing import Iterable

from app.real_markets.connectors import (
    ReadOnlyMarketConnector,
)


class RealMarketConnectorRegistry:
    """Registro central de conectores somente leitura."""

    def __init__(self) -> None:
        self._connectors: dict[
            str,
            ReadOnlyMarketConnector,
        ] = {}
        self._lock = threading.RLock()

    def register(
        self,
        connector: ReadOnlyMarketConnector,
        *,
        replace: bool = False,
    ) -> None:
        connector_id = (
            connector.connector_id.strip()
        )

        if not connector_id:
            raise ValueError(
                "connector_id é obrigatório."
            )

        if connector.read_only is not True:
            raise ValueError(
                "A Fase 9A aceita apenas conectores "
                "somente leitura."
            )

        with self._lock:
            if (
                connector_id in self._connectors
                and not replace
            ):
                raise ValueError(
                    "Conector já registrado: "
                    f"{connector_id}"
                )

            self._connectors[
                connector_id
            ] = connector

    def unregister(
        self,
        connector_id: str,
    ) -> bool:
        with self._lock:
            return (
                self._connectors.pop(
                    connector_id,
                    None,
                )
                is not None
            )

    def get(
        self,
        connector_id: str,
    ) -> ReadOnlyMarketConnector:
        with self._lock:
            connector = self._connectors.get(
                connector_id
            )

        if connector is None:
            raise KeyError(
                "Conector não registrado: "
                f"{connector_id}"
            )

        return connector

    def list(
        self,
    ) -> list[ReadOnlyMarketConnector]:
        with self._lock:
            return [
                self._connectors[key]
                for key in sorted(
                    self._connectors
                )
            ]

    def descriptors(
        self,
    ) -> list[dict]:
        return [
            connector.descriptor()
            for connector in self.list()
        ]

    def __len__(
        self,
    ) -> int:
        with self._lock:
            return len(
                self._connectors
            )

    def __iter__(
        self,
    ) -> Iterable[
        ReadOnlyMarketConnector
    ]:
        return iter(
            self.list()
        )
