"""Transporte WebSocket somente de leitura.

A função de conexão é injetável e a importação de `websockets` é
tardia, dentro do factory padrão. Duas razões:

1. os testes substituem a conexão por um duplo e exercitam o
   caminho real sem abrir socket;
2. a API pública da biblioteca mudou de lugar entre versões, e
   isolar o import num único ponto evita que uma atualização
   quebre a importação do pacote inteiro.

`ping_interval` e `ping_timeout` são explícitos porque conexão de
market data que morre em silêncio é pior do que conexão que cai:
sem heartbeat, o livro local continua parecendo saudável enquanto
para de receber atualização.
"""

from __future__ import annotations

import json
from typing import Any, Awaitable, Callable

from app.crypto_arbitrage.domain.errors import (
    TransportError,
)
from app.crypto_arbitrage.market_data.metrics import (
    ConnectorMetrics,
)


ConnectFactory = Callable[..., Awaitable[Any]]


async def _default_connect(
    url: str,
    *,
    ping_interval: float,
    ping_timeout: float,
    open_timeout: float,
) -> Any:
    from websockets import connect as websockets_connect

    return await websockets_connect(
        url,
        ping_interval=ping_interval,
        ping_timeout=ping_timeout,
        open_timeout=open_timeout,
    )


class WebsocketsTransport:
    """Implementa `WebSocketTransport` com a lib `websockets`."""

    def __init__(
        self,
        *,
        connect_factory: ConnectFactory | None = None,
        metrics: ConnectorMetrics | None = None,
        ping_interval: float = 20.0,
        ping_timeout: float = 20.0,
        open_timeout: float = 10.0,
    ) -> None:
        self._connect_factory = (
            connect_factory or _default_connect
        )
        self._metrics = metrics
        self._ping_interval = float(ping_interval)
        self._ping_timeout = float(ping_timeout)
        self._open_timeout = float(open_timeout)
        self._connection: Any = None

    @property
    def is_connected(self) -> bool:
        return self._connection is not None

    async def connect(self, url: str) -> None:
        if self._connection is not None:
            raise TransportError(
                "Conexão já aberta. Feche antes de reabrir."
            )

        try:
            self._connection = (
                await self._connect_factory(
                    url,
                    ping_interval=self._ping_interval,
                    ping_timeout=self._ping_timeout,
                    open_timeout=self._open_timeout,
                )
            )
        except Exception as exc:
            self._record_error(str(exc))

            raise TransportError(
                f"Não foi possível conectar em {url}: {exc}"
            ) from exc

    async def send_json(self, payload: Any) -> None:
        connection = self._require_connection()

        try:
            await connection.send(json.dumps(payload))
        except Exception as exc:
            self._record_error(str(exc))

            raise TransportError(
                f"Falha ao enviar mensagem: {exc}"
            ) from exc

    async def receive_json(self) -> Any:
        connection = self._require_connection()

        try:
            raw = await connection.recv()
        except Exception as exc:
            self._record_error(str(exc))

            raise TransportError(
                f"Falha ao receber mensagem: {exc}"
            ) from exc

        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")

        try:
            return json.loads(raw)
        except ValueError as exc:
            self._record_error("Mensagem não-JSON.")

            raise TransportError(
                "Mensagem recebida não é JSON válido."
            ) from exc

    async def close(self) -> None:
        connection = self._connection
        self._connection = None

        if connection is None:
            return

        try:
            await connection.close()
        except Exception as exc:
            # Fechar e best-effort: se o socket ja morreu, o
            # objetivo de nao reutiliza-lo ja foi atingido.
            self._record_error(str(exc))

    def _require_connection(self) -> Any:
        if self._connection is None:
            raise TransportError(
                "Nenhuma conexão aberta."
            )

        return self._connection

    def _record_error(self, detail: str) -> None:
        if self._metrics is not None:
            self._metrics.record_error(detail)
