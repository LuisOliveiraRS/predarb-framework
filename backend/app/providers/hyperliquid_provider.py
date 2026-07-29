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

    async def get_account_snapshot(
        self,
        user: str,
        *,
        dex: str = "",
    ) -> dict[str, Any]:
        """
        Recupera um snapshot real da conta
        usando apenas o endereco publico.

        Nenhuma assinatura, chave privada ou
        endpoint de execucao e utilizado.
        """

        started_at = perf_counter()

        normalized_user = (
            self.client.normalize_user_address(
                user
            )
        )

        role = await self.client.user_role(
            normalized_user
        )

        perpetual = (
            await self.client
            .clearinghouse_state(
                normalized_user,
                dex=dex,
            )
        )

        spot = (
            await self.client
            .spot_clearinghouse_state(
                normalized_user
            )
        )

        open_orders = (
            await self.client.open_orders(
                normalized_user,
                dex=dex,
            )
        )

        fills = await self.client.user_fills(
            normalized_user,
            aggregate_by_time=True,
        )

        portfolio = (
            await self.client.portfolio(
                normalized_user
            )
        )

        latency = (
            perf_counter()
            - started_at
        ) * 1000

        perpetual_positions = (
            perpetual.get(
                "assetPositions",
                [],
            )
            if isinstance(
                perpetual,
                Mapping,
            )
            else []
        )

        spot_balances = (
            spot.get(
                "balances",
                [],
            )
            if isinstance(
                spot,
                Mapping,
            )
            else []
        )

        snapshot = {
            "status": "online",
            "connector": "hyperliquid",
            "account_address": (
                normalized_user
            ),
            "dex": dex.strip(),
            "latency": round(
                latency,
                3,
            ),
            "role": role,
            "perpetual": perpetual,
            "spot": spot,
            "open_orders": open_orders,
            "fills": fills,
            "portfolio": portfolio,
            "summary": {
                "perpetual_positions": (
                    len(perpetual_positions)
                    if isinstance(
                        perpetual_positions,
                        list,
                    )
                    else 0
                ),
                "spot_balances": (
                    len(spot_balances)
                    if isinstance(
                        spot_balances,
                        list,
                    )
                    else 0
                ),
                "open_orders": len(
                    open_orders
                ),
                "fills": len(
                    fills
                ),
                "portfolio_entries": len(
                    portfolio
                ),
            },
            "account_data_real": True,
            "public_address_only": True,
            "read_only": True,
            "wallet_signing": False,
            "private_key_access": False,
            "credential_access": False,
            "exchange_endpoint_available": False,
            "order_submission_available": False,
            "execution_authorized": False,
            "live_execution": False,
            "financial_execution": False,
            "automatic_execution_authorized": False,
            "next_step_authorized": False,
        }

        return snapshot

    async def close(self) -> None:
        """
        Encerra recursos externos quando aplicável.
        """

        await self.client.close()


hyperliquid_provider = HyperliquidProvider()