from __future__ import annotations

import asyncio
import logging
from collections.abc import Mapping
from time import perf_counter
from typing import Any

from app.clients.hyperliquid import (
    HyperliquidClient,
    hyperliquid_client,
)


logger = logging.getLogger(__name__)


class HyperliquidProvider:
    """
    Provider responsável pela comunicação com
    os endpoints públicos da Hyperliquid.

    Esta camada não conhece Repository, Pipeline
    ou regras de arbitragem.
    """

    def __init__(
        self,
        client: HyperliquidClient | None = None,
    ) -> None:
        self.client = (
            client
            or hyperliquid_client
        )

        self._last_metadata_error: str | None = None

    @property
    def last_metadata_error(
        self,
    ) -> str | None:
        return self._last_metadata_error

    async def health(
        self,
    ) -> dict[str, Any]:
        """
        Verifica a conectividade por meio
        do endpoint allMids.
        """

        started_at = perf_counter()

        try:
            mids = await self.client.all_mids()

        except Exception as exc:
            latency = (
                perf_counter() - started_at
            ) * 1000

            return {
                "status": "error",
                "connected": False,
                "connector": "hyperliquid",
                "latency": round(
                    latency,
                    3,
                ),
                "assets": 0,
                "error": str(exc),
            }

        latency = (
            perf_counter() - started_at
        ) * 1000

        return {
            "status": "online",
            "connected": True,
            "connector": "hyperliquid",
            "latency": round(
                latency,
                3,
            ),
            "assets": len(mids),
            "metadata_error": (
                self._last_metadata_error
            ),
            "error": None,
        }

    async def get_outcome_snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Recupera simultaneamente:

        - metadados HIP-4;
        - preços médios disponíveis.

        Caso outcomeMeta não esteja disponível no
        ambiente selecionado, retorna uma coleção
        vazia de outcomes sem interromper allMids.
        """

        metadata_result, mids_result = (
            await asyncio.gather(
                self.client.outcome_meta(),
                self.client.all_mids(),
                return_exceptions=True,
            )
        )

        if isinstance(
            mids_result,
            BaseException,
        ):
            raise RuntimeError(
                "Não foi possível obter allMids "
                "da Hyperliquid."
            ) from mids_result

        if not isinstance(
            mids_result,
            Mapping,
        ):
            raise TypeError(
                "allMids retornou um formato inválido."
            )

        metadata_error: str | None = None

        if isinstance(
            metadata_result,
            BaseException,
        ):
            metadata_error = str(
                metadata_result
            )

            metadata: dict[str, Any] = {
                "outcomes": [],
            }

            logger.warning(
                "outcomeMeta indisponível: %s",
                metadata_error,
            )

        elif isinstance(
            metadata_result,
            Mapping,
        ):
            metadata = dict(
                metadata_result
            )

        else:
            metadata_error = (
                "outcomeMeta retornou um "
                "formato inesperado."
            )

            metadata = {
                "outcomes": [],
            }

        self._last_metadata_error = (
            metadata_error
        )

        return {
            "metadata": metadata,
            "mids": dict(mids_result),
            "metadata_error": metadata_error,
        }

    async def get_all_markets(
        self,
    ) -> dict[str, Any]:
        """
        Preserva o método público anterior.

        Agora retorna um snapshot completo contendo
        metadados e preços dos outcomes.
        """

        return await self.get_outcome_snapshot()

    async def close(self) -> None:
        """
        Encerra recursos externos quando aplicável.
        """

        await self.client.close()


hyperliquid_provider = HyperliquidProvider()