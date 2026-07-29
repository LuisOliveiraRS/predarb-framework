from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.core.settings import settings
from app.http.client import (
    HttpClient,
    http_client,
)


class HyperliquidClient:
    """
    Cliente da API pública da Hyperliquid.

    Este componente conhece somente os endpoints
    externos. Não contém regras de arbitragem.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        client: HttpClient | None = None,
    ) -> None:
        resolved_url = (
            base_url
            or settings.HYPERLIQUID_API_URL
        )

        if not isinstance(resolved_url, str):
            raise TypeError(
                "A URL da Hyperliquid deve "
                "ser uma string."
            )

        resolved_url = resolved_url.strip()

        if not resolved_url:
            raise ValueError(
                "A URL da Hyperliquid não "
                "pode ser vazia."
            )

        self.base_url = resolved_url.rstrip("/")
        self.http_client = client or http_client

    async def info(
        self,
        payload: Mapping[str, Any],
    ) -> Any:
        """
        Executa uma consulta no endpoint /info.
        """

        if not isinstance(payload, Mapping):
            raise TypeError(
                "O payload da Hyperliquid deve "
                "ser um objeto Mapping."
            )

        request_payload = dict(payload)

        request_type = request_payload.get(
            "type"
        )

        if (
            not isinstance(request_type, str)
            or not request_type.strip()
        ):
            raise ValueError(
                "O payload da Hyperliquid deve "
                "possuir um campo type válido."
            )

        return await self.http_client.post(
            f"{self.base_url}/info",
            request_payload,
        )

    async def all_mids(
        self,
    ) -> dict[str, Any]:
        """
        Recupera os preços médios disponíveis.
        """

        response = await self.info(
            {
                "type": "allMids",
            }
        )

        if not isinstance(response, Mapping):
            raise TypeError(
                "allMids retornou um formato "
                "inesperado."
            )

        return dict(response)

    async def outcome_meta(
        self,
    ) -> dict[str, Any]:
        """
        Recupera os metadados dos mercados
        de resultado HIP-4.
        """

        response = await self.info(
            {
                "type": "outcomeMeta",
            }
        )

        if not isinstance(response, Mapping):
            raise TypeError(
                "outcomeMeta retornou um formato "
                "inesperado."
            )

        return dict(response)

    async def close(self) -> None:
        """
        Encerra recursos HTTP quando aplicável.
        """

        await self.http_client.close()


hyperliquid_client = HyperliquidClient()