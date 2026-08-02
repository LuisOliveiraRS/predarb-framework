"""Contratos de transporte para conectores públicos.

O transporte é injetado, nunca instanciado aqui. Isso mantém a
orquestração testável sem rede, como a seção 28 do CLAUDE.md
exige para os testes padrão, e deixa a escolha de biblioteca
concentrada num único ponto.

Nenhum transporte deste módulo carrega credencial. Conectores
públicos não devem sequer ter como assinar uma requisição.
"""

from __future__ import annotations

from typing import Any, Mapping, Protocol, runtime_checkable


@runtime_checkable
class RestTransport(Protocol):
    """Requisições HTTP somente de leitura."""

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any: ...


@runtime_checkable
class WebSocketTransport(Protocol):
    """Canal WebSocket bidirecional para dados públicos.

    `send_json` existe apenas para inscrição e ping. Não é, e não
    deve virar, caminho de envio de ordem: venues usam endpoints
    e autenticação separados para isso, e o registry recusa
    qualquer conector com capacidade de execução.
    """

    @property
    def is_connected(self) -> bool: ...

    async def connect(self, url: str) -> None: ...

    async def send_json(self, payload: Any) -> None: ...

    async def receive_json(self) -> Any: ...

    async def close(self) -> None: ...
