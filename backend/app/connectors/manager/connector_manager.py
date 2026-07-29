from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from threading import RLock
from time import perf_counter
from typing import Any

from app.connectors.models.status import (
    ConnectorStatus,
)
from app.repositories.market_repository import (
    market_repository,
)


logger = logging.getLogger(__name__)


class ConnectorManager:
    """
    Registro e orquestrador oficial dos conectores.

    Responsabilidades:

    - registrar e localizar conectores;
    - controlar conexão e desconexão em lote;
    - executar diagnósticos sem interromper os demais;
    - coletar mercados de forma concorrente;
    - substituir o conteúdo do MarketRepository
      uma única vez.
    """

    REQUIRED_METHODS = (
        "connect",
        "disconnect",
        "get_markets",
        "health",
    )

    def __init__(self) -> None:
        # Mantido público para compatibilidade
        # com o código existente.
        self.connectors: dict[str, Any] = {}

        self._statuses: dict[
            str,
            ConnectorStatus,
        ] = {}

        self._lock = RLock()

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Valida e normaliza o nome do conector.
        """

        if not isinstance(
            name,
            str,
        ):
            raise TypeError(
                "O nome do conector deve "
                "ser uma string."
            )

        normalized = name.strip().lower()

        if not normalized:
            raise ValueError(
                "O nome do conector não "
                "pode ser vazio."
            )

        return normalized

    @classmethod
    def _validate_connector(
        cls,
        connector: Any,
    ) -> None:
        """
        Valida o contrato mínimo de um conector.
        """

        if connector is None:
            raise ValueError(
                "Não é possível registrar "
                "um conector None."
            )

        missing = [
            method_name
            for method_name in cls.REQUIRED_METHODS
            if not callable(
                getattr(
                    connector,
                    method_name,
                    None,
                )
            )
        ]

        if missing:
            methods = ", ".join(
                missing
            )

            raise TypeError(
                "O conector não implementa "
                "o contrato obrigatório: "
                f"{methods}."
            )

    def register(
        self,
        name: str,
        connector: Any,
        *,
        replace: bool = True,
    ) -> Any:
        """
        Registra um conector e retorna
        a própria instância.
        """

        normalized_name = self._normalize_name(
            name
        )

        self._validate_connector(
            connector
        )

        with self._lock:
            current = self.connectors.get(
                normalized_name
            )

            if current is connector:
                return connector

            if (
                current is not None
                and not replace
            ):
                raise KeyError(
                    "Já existe um conector "
                    "registrado com o nome: "
                    f"{normalized_name}"
                )

            self.connectors[
                normalized_name
            ] = connector

            self._statuses[
                normalized_name
            ] = ConnectorStatus(
                name=normalized_name,
            )

        logger.info(
            "Conector registrado: %s",
            normalized_name,
        )

        return connector

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um conector pelo nome.
        """

        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            return self.connectors.get(
                normalized_name,
                default,
            )

    def require(
        self,
        name: str,
    ) -> Any:
        """
        Recupera um conector obrigatório.
        """

        normalized_name = self._normalize_name(
            name
        )

        connector = self.get(
            normalized_name
        )

        if connector is None:
            raise LookupError(
                "Conector não registrado: "
                f"{normalized_name}"
            )

        return connector

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Verifica se um conector está registrado.
        """

        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            return (
                normalized_name
                in self.connectors
            )

    def unregister(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Remove um conector do registro.
        """

        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            self._statuses.pop(
                normalized_name,
                None,
            )

            return self.connectors.pop(
                normalized_name,
                default,
            )

    def all(
        self,
    ) -> dict[str, Any]:
        """
        Retorna uma cópia do registro atual.
        """

        with self._lock:
            return dict(
                self.connectors
            )

    def names(
        self,
    ) -> list[str]:
        """
        Retorna os nomes dos conectores registrados.
        """

        with self._lock:
            return list(
                self.connectors.keys()
            )

    def clear(
        self,
    ) -> None:
        """
        Limpa o registro sem controlar
        o ciclo de vida externo.
        """

        with self._lock:
            self.connectors.clear()
            self._statuses.clear()

    def _status_for(
        self,
        name: str,
    ) -> ConnectorStatus:
        """
        Recupera ou cria o estado interno
        de um conector.
        """

        with self._lock:
            status = self._statuses.get(
                name
            )

            if status is None:
                status = ConnectorStatus(
                    name=name
                )

                self._statuses[
                    name
                ] = status

            return status

    @staticmethod
    def _parse_datetime(
        value: Any,
    ) -> datetime | str | None:
        """
        Normaliza datas recebidas dos conectores.
        """

        if (
            value is None
            or isinstance(
                value,
                datetime,
            )
        ):
            return value

        if isinstance(
            value,
            str,
        ):
            normalized = value.strip()

            if not normalized:
                return None

            try:
                return datetime.fromisoformat(
                    normalized
                )

            except ValueError:
                return normalized

        return str(value)

    @staticmethod
    def _as_market_list(
        value: Any,
        connector_name: str,
    ) -> list[Any]:
        """
        Garante que get_markets() retornou
        uma coleção válida.
        """

        if value is None:
            return []

        if isinstance(
            value,
            Mapping,
        ):
            raise TypeError(
                f"O conector {connector_name!r} "
                "retornou um objeto único; "
                "get_markets() deve retornar "
                "uma coleção."
            )

        if isinstance(
            value,
            (str, bytes),
        ):
            raise TypeError(
                f"O conector {connector_name!r} "
                "retornou texto em vez de mercados."
            )

        try:
            return list(value)

        except TypeError as exc:
            raise TypeError(
                f"O conector {connector_name!r} "
                "deve retornar uma coleção "
                "de mercados."
            ) from exc

    async def _connect_one(
        self,
        name: str,
        connector: Any,
    ) -> tuple[str, ConnectorStatus]:
        """
        Conecta um único conector.
        """

        status = self._status_for(
            name
        )

        started_at = perf_counter()

        try:
            result = await connector.connect()

            status.connected = (
                result is not False
            )

            status.error = (
                None
                if status.connected
                else "connect() retornou False."
            )

        except Exception as exc:
            status.connected = False
            status.error = str(exc)

            logger.exception(
                "Erro ao conectar %s.",
                name,
            )

        status.latency = (
            perf_counter() - started_at
        ) * 1000

        return name, status

    async def connect_all(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Conecta todos os conectores sem
        interromper o lote.
        """

        connectors = self.all()

        results = await asyncio.gather(
            *(
                self._connect_one(
                    name,
                    connector,
                )
                for name, connector
                in connectors.items()
            )
        )

        return {
            name: status.to_dict()
            for name, status in results
        }

    async def _disconnect_one(
        self,
        name: str,
        connector: Any,
    ) -> tuple[str, ConnectorStatus]:
        """
        Desconecta um único conector.
        """

        status = self._status_for(
            name
        )

        started_at = perf_counter()

        try:
            result = (
                await connector.disconnect()
            )

            if result is False:
                status.error = (
                    "disconnect() retornou False."
                )

            else:
                status.connected = False
                status.error = None

        except Exception as exc:
            status.error = str(exc)

            logger.exception(
                "Erro ao desconectar %s.",
                name,
            )

        status.latency = (
            perf_counter() - started_at
        ) * 1000

        return name, status

    async def disconnect_all(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Desconecta todos os conectores sem
        interromper o lote.
        """

        connectors = self.all()

        results = await asyncio.gather(
            *(
                self._disconnect_one(
                    name,
                    connector,
                )
                for name, connector
                in connectors.items()
            )
        )

        return {
            name: status.to_dict()
            for name, status in results
        }

    @staticmethod
    def _connected_from_health(
        raw_status: Any,
    ) -> bool:
        """
        Interpreta respostas distintas de health().
        """

        if isinstance(
            raw_status,
            ConnectorStatus,
        ):
            return raw_status.connected

        if isinstance(
            raw_status,
            Mapping,
        ):
            connected = raw_status.get(
                "connected"
            )

            if isinstance(
                connected,
                bool,
            ):
                return connected

            status_name = str(
                raw_status.get(
                    "status",
                    "",
                )
            ).strip().lower()

            if status_name in {
                "online",
                "healthy",
                "connected",
                "ok",
                "up",
            }:
                return True

            if status_name in {
                "offline",
                "unhealthy",
                "error",
                "down",
            }:
                return False

            return (
                bool(raw_status)
                and not raw_status.get(
                    "error"
                )
            )

        return bool(raw_status)

    async def _health_one(
        self,
        name: str,
        connector: Any,
    ) -> tuple[str, ConnectorStatus]:
        """
        Executa o health check de um conector.
        """

        status = self._status_for(
            name
        )

        started_at = perf_counter()

        try:
            raw_status = (
                await connector.health()
            )

            status.connected = (
                self._connected_from_health(
                    raw_status
                )
            )

            status.error = None

            if isinstance(
                raw_status,
                ConnectorStatus,
            ):
                status.last_update = (
                    raw_status.last_update
                )

                status.markets = (
                    raw_status.markets
                )

                status.error = (
                    raw_status.error
                )

                status.details = dict(
                    raw_status.details
                )

            elif isinstance(
                raw_status,
                Mapping,
            ):
                status.last_update = (
                    self._parse_datetime(
                        raw_status.get(
                            "last_update",
                            status.last_update,
                        )
                    )
                )

                markets = raw_status.get(
                    "markets",
                    status.markets,
                )

                try:
                    status.markets = max(
                        0,
                        int(markets or 0),
                    )

                except (
                    TypeError,
                    ValueError,
                ):
                    pass

                raw_error = raw_status.get(
                    "error"
                )

                status.error = (
                    str(raw_error)
                    if raw_error
                    else None
                )

                status.details = dict(
                    raw_status
                )

        except Exception as exc:
            status.connected = False
            status.error = str(exc)

            logger.exception(
                "Erro no health check de %s.",
                name,
            )

        status.latency = (
            perf_counter() - started_at
        ) * 1000

        return name, status

    async def health(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Executa health checks concorrentes
        e padroniza a resposta.
        """

        connectors = self.all()

        results = await asyncio.gather(
            *(
                self._health_one(
                    name,
                    connector,
                )
                for name, connector
                in connectors.items()
            )
        )

        return {
            name: status.to_dict()
            for name, status in results
        }

    async def _fetch_markets(
        self,
        name: str,
        connector: Any,
    ) -> tuple[
        str,
        bool,
        list[Any],
        str | None,
    ]:
        """
        Coleta mercados de um conector.
        """

        status = self._status_for(
            name
        )

        started_at = perf_counter()

        try:
            raw_markets = (
                await connector.get_markets()
            )

            markets = self._as_market_list(
                raw_markets,
                name,
            )

            status.connected = True

            status.last_update = datetime.now(
                timezone.utc,
            )

            status.markets = len(
                markets
            )

            status.error = None

            status.latency = (
                perf_counter() - started_at
            ) * 1000

            return (
                name,
                True,
                markets,
                None,
            )

        except Exception as exc:
            status.error = str(exc)

            status.latency = (
                perf_counter() - started_at
            ) * 1000

            logger.exception(
                "Erro ao atualizar mercados "
                "do conector %s.",
                name,
            )

            return (
                name,
                False,
                [],
                str(exc),
            )

    async def update_markets(
        self,
        *,
        persist: bool = True,
        raise_on_error: bool = False,
    ) -> list[Any]:
        """
        Coleta mercados de todos os conectores.

        O repositório é atualizado somente depois
        que todas as coletas terminam, evitando
        um estado parcialmente limpo.
        """

        connectors = self.all()

        if not connectors:
            if persist:
                market_repository.save_all(
                    []
                )

            return []

        results = await asyncio.gather(
            *(
                self._fetch_markets(
                    name,
                    connector,
                )
                for name, connector
                in connectors.items()
            )
        )

        markets: list[Any] = []

        errors: dict[
            str,
            str,
        ] = {}

        successful_connectors = 0

        for (
            name,
            success,
            connector_markets,
            error,
        ) in results:
            if success:
                successful_connectors += 1

                markets.extend(
                    connector_markets
                )

            elif error:
                errors[name] = error

        if (
            persist
            and successful_connectors
        ):
            market_repository.save_all(
                markets
            )

        if (
            errors
            and raise_on_error
        ):
            details = "; ".join(
                f"{name}: {error}"
                for name, error
                in errors.items()
            )

            raise RuntimeError(
                "Falha ao atualizar um ou "
                "mais conectores: "
                f"{details}"
            )

        if not successful_connectors:
            logger.warning(
                "Nenhum conector concluiu "
                "a atualização; o "
                "MarketRepository foi preservado."
            )

        return markets

    def status(
        self,
        name: str,
    ) -> dict[str, Any]:
        """
        Retorna o último estado conhecido
        de um conector.
        """

        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            status = self._statuses.get(
                normalized_name
            )

            if status is None:
                raise LookupError(
                    "Conector não registrado: "
                    f"{normalized_name}"
                )

            return status.to_dict()

    def statuses(
        self,
    ) -> dict[str, dict[str, Any]]:
        """
        Retorna os últimos estados conhecidos
        de todos os conectores.
        """

        with self._lock:
            return {
                name: status.to_dict()
                for name, status
                in self._statuses.items()
            }


connector_manager = ConnectorManager()