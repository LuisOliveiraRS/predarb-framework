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

    @staticmethod
    def normalize_user_address(
        user: str,
    ) -> str:
        """
        Valida e normaliza um endere?o p?blico
        usado apenas nas consultas do endpoint
        informativo da Hyperliquid.
        """

        if not isinstance(
            user,
            str,
        ):
            raise TypeError(
                "O endere?o da conta Hyperliquid "
                "deve ser uma string."
            )

        normalized = user.strip()

        if (
            len(normalized) != 42
            or not normalized.startswith(
                (
                    "0x",
                    "0X",
                )
            )
        ):
            raise ValueError(
                "O endere?o da conta Hyperliquid "
                "deve possuir 42 caracteres e "
                "iniciar com 0x."
            )

        hexadecimal = normalized[2:]

        try:
            int(
                hexadecimal,
                16,
            )

        except ValueError as exc:
            raise ValueError(
                "O endere?o da conta Hyperliquid "
                "possui caracteres inv?lidos."
            ) from exc

        return (
            "0x"
            + hexadecimal.lower()
        )

    @staticmethod
    def _normalize_dex(
        dex: str,
    ) -> str:
        if not isinstance(
            dex,
            str,
        ):
            raise TypeError(
                "O nome da DEX Hyperliquid "
                "deve ser uma string."
            )

        return dex.strip()

    async def clearinghouse_state(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> dict[str, Any]:
        """
        Consulta posi??es e margem de perp?tuos.
        N?o assina nem envia transa??es.
        """

        payload: dict[str, Any] = {
            "type": "clearinghouseState",
            "user": self.normalize_user_address(
                user
            ),
        }

        normalized_dex = (
            self._normalize_dex(
                dex
            )
        )

        if normalized_dex:
            payload["dex"] = normalized_dex

        response = await self.info(
            payload
        )

        if not isinstance(
            response,
            Mapping,
        ):
            raise TypeError(
                "clearinghouseState retornou "
                "um formato inesperado."
            )

        return dict(
            response
        )

    async def spot_clearinghouse_state(
        self,
        user: str,
    ) -> dict[str, Any]:
        """
        Consulta os saldos spot da conta.
        """

        response = await self.info(
            {
                "type": (
                    "spotClearinghouseState"
                ),
                "user": (
                    self.normalize_user_address(
                        user
                    )
                ),
            }
        )

        if not isinstance(
            response,
            Mapping,
        ):
            raise TypeError(
                "spotClearinghouseState retornou "
                "um formato inesperado."
            )

        return dict(
            response
        )

    async def open_orders(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> list[dict[str, Any]]:
        """
        Consulta ordens abertas sem modific?-las.
        """

        payload: dict[str, Any] = {
            "type": "openOrders",
            "user": self.normalize_user_address(
                user
            ),
        }

        normalized_dex = (
            self._normalize_dex(
                dex
            )
        )

        if normalized_dex:
            payload["dex"] = normalized_dex

        response = await self.info(
            payload
        )

        if not isinstance(
            response,
            list,
        ):
            raise TypeError(
                "openOrders retornou "
                "um formato inesperado."
            )

        if not all(
            isinstance(
                item,
                Mapping,
            )
            for item in response
        ):
            raise TypeError(
                "openOrders retornou um item "
                "com formato inesperado."
            )

        return [
            dict(item)
            for item in response
        ]

    async def user_fills(
        self,
        user: str,
        *,
        aggregate_by_time: bool = True,
    ) -> list[dict[str, Any]]:
        """
        Consulta as execu??es recentes da conta.
        """

        if not isinstance(
            aggregate_by_time,
            bool,
        ):
            raise TypeError(
                "aggregate_by_time deve "
                "ser booleano."
            )

        response = await self.info(
            {
                "type": "userFills",
                "user": (
                    self.normalize_user_address(
                        user
                    )
                ),
                "aggregateByTime": (
                    aggregate_by_time
                ),
            }
        )

        if not isinstance(
            response,
            list,
        ):
            raise TypeError(
                "userFills retornou "
                "um formato inesperado."
            )

        if not all(
            isinstance(
                item,
                Mapping,
            )
            for item in response
        ):
            raise TypeError(
                "userFills retornou um item "
                "com formato inesperado."
            )

        return [
            dict(item)
            for item in response
        ]

    async def portfolio(
        self,
        user: str,
    ) -> list[Any]:
        """
        Consulta o hist?rico consolidado
        de valor da conta.
        """

        response = await self.info(
            {
                "type": "portfolio",
                "user": (
                    self.normalize_user_address(
                        user
                    )
                ),
            }
        )

        if not isinstance(
            response,
            list,
        ):
            raise TypeError(
                "portfolio retornou "
                "um formato inesperado."
            )

        return list(
            response
        )

    async def user_role(
        self,
        user: str,
    ) -> dict[str, Any]:
        """
        Identifica conta principal, agente,
        vault, subconta ou endere?o ausente.
        """

        response = await self.info(
            {
                "type": "userRole",
                "user": (
                    self.normalize_user_address(
                        user
                    )
                ),
            }
        )

        if not isinstance(
            response,
            Mapping,
        ):
            raise TypeError(
                "userRole retornou "
                "um formato inesperado."
            )

        return dict(
            response
        )

    async def close(self) -> None:
        """
        Encerra recursos HTTP quando aplicável.
        """

        await self.http_client.close()


hyperliquid_client = HyperliquidClient()