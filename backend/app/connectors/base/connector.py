from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime, timezone
from typing import Any

from app.connectors.models.status import ConnectorStatus


class BaseConnector(ABC):
    """
    Contrato oficial para conectores do PredArb.

    Todo conector deve implementar seu ciclo de vida,
    a coleta de mercados e o diagnóstico de saúde.
    """

    name: str = ""

    @property
    def connector_name(self) -> str:
        """
        Retorna o identificador normalizado
        do conector.
        """

        configured_name = getattr(
            self,
            "name",
            "",
        )

        if (
            isinstance(configured_name, str)
            and configured_name.strip()
        ):
            return configured_name.strip().lower()

        class_name = self.__class__.__name__

        if class_name.lower().endswith(
            "connector"
        ):
            class_name = class_name[:-9]

        return class_name.strip().lower()

    @property
    def connected(self) -> bool:
        """
        Indica o último estado de conexão conhecido.
        """

        return bool(
            getattr(
                self,
                "_connected",
                False,
            )
        )

    @connected.setter
    def connected(
        self,
        value: bool,
    ) -> None:
        self._connected = bool(value)

    @property
    def last_update(
        self,
    ) -> datetime | str | None:
        """
        Retorna a última atualização conhecida.
        """

        return getattr(
            self,
            "_last_update",
            None,
        )

    @last_update.setter
    def last_update(
        self,
        value: datetime | str | None,
    ) -> None:
        self._last_update = value

    @property
    def market_count(self) -> int:
        """
        Retorna a última quantidade de
        mercados coletada.
        """

        value = getattr(
            self,
            "_market_count",
            0,
        )

        try:
            return max(
                0,
                int(value),
            )

        except (
            TypeError,
            ValueError,
        ):
            return 0

    @market_count.setter
    def market_count(
        self,
        value: int,
    ) -> None:
        self._market_count = max(
            0,
            int(value),
        )

    def mark_connected(
        self,
        connected: bool = True,
    ) -> None:
        """
        Atualiza o estado interno de conexão.
        """

        self._connected = bool(
            connected
        )

        if connected:
            self._last_error = None

    def mark_updated(
        self,
        market_count: int,
        *,
        updated_at: datetime | str | None = None,
    ) -> None:
        """
        Registra uma coleta concluída
        pelo conector.
        """

        self._market_count = max(
            0,
            int(market_count),
        )

        self._last_update = (
            updated_at
            or datetime.now(
                timezone.utc,
            )
        )

        self._last_error = None

    def mark_error(
        self,
        error: Exception | str,
    ) -> None:
        """
        Registra o último erro operacional.
        """

        self._last_error = str(error)

    def get_status(
        self,
    ) -> ConnectorStatus:
        """
        Retorna o estado básico do conector.
        """

        return ConnectorStatus(
            name=self.connector_name,
            connected=self.connected,
            last_update=self.last_update,
            markets=self.market_count,
            error=getattr(
                self,
                "_last_error",
                None,
            ),
        )

    @abstractmethod
    async def connect(
        self,
    ) -> bool | None:
        """
        Inicializa os recursos externos
        do conector.
        """

        raise NotImplementedError

    @abstractmethod
    async def disconnect(
        self,
    ) -> bool | None:
        """
        Libera os recursos externos
        do conector.
        """

        raise NotImplementedError

    @abstractmethod
    async def get_markets(
        self,
    ) -> list[Any]:
        """
        Retorna mercados no formato
        aceito pela aplicação.
        """

        raise NotImplementedError

    @abstractmethod
    async def health(
        self,
    ) -> ConnectorStatus | dict[str, Any] | bool:
        """
        Retorna o diagnóstico atual
        do conector.
        """

        raise NotImplementedError

    async def __aenter__(
        self,
    ) -> BaseConnector:
        await self.connect()

        return self

    async def __aexit__(
        self,
        exc_type: Any,
        exc: BaseException | None,
        traceback: Any,
    ) -> None:
        await self.disconnect()