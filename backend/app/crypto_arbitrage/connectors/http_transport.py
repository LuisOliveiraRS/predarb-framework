"""Transporte REST somente de leitura, sobre httpx.

O cliente `httpx.AsyncClient` é injetado, nunca criado aqui. Quem
constrói o cliente decide timeout, proxy e limites de conexão, e
os testes injetam `httpx.MockTransport` para exercitar o caminho
real de parsing sem tocar a rede.

Este transporte não conhece credencial. Conectores públicos não
devem ter como assinar requisição, conforme a invariante 8 da
seção 8 do CLAUDE.md.
"""

from __future__ import annotations

from typing import Any, Mapping

import httpx

from app.crypto_arbitrage.domain.errors import (
    RateLimitExceededError,
    TransportError,
)
from app.crypto_arbitrage.market_data.metrics import (
    ConnectorMetrics,
)
from app.crypto_arbitrage.market_data.rate_limiter import (
    TokenBucketRateLimiter,
)


class HttpxRestTransport:
    """Implementa `RestTransport` com httpx."""

    def __init__(
        self,
        client: httpx.AsyncClient,
        *,
        rate_limiter: TokenBucketRateLimiter | None = None,
        metrics: ConnectorMetrics | None = None,
    ) -> None:
        self._client = client
        self._rate_limiter = rate_limiter
        self._metrics = metrics

    async def get_json(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
    ) -> Any:
        self._check_rate_limit()

        try:
            response = await self._client.get(
                url,
                params=dict(params) if params else None,
            )
        except httpx.HTTPError as exc:
            self._record_error(str(exc))

            raise TransportError(
                f"Falha de rede em {url}: {exc}"
            ) from exc

        if response.status_code == 429:
            self._record_rate_limit()

            raise RateLimitExceededError(
                f"A venue recusou por rate limit em {url}. "
                "Reduza a frequência antes de tentar de novo."
            )

        if response.status_code >= 400:
            self._record_error(
                f"HTTP {response.status_code} em {url}"
            )

            raise TransportError(
                f"HTTP {response.status_code} em {url}."
            )

        try:
            return response.json()
        except ValueError as exc:
            self._record_error(
                f"Resposta não-JSON em {url}"
            )

            raise TransportError(
                f"Resposta ilegível em {url}."
            ) from exc

    def _check_rate_limit(self) -> None:
        if self._rate_limiter is None:
            return

        if self._rate_limiter.try_acquire():
            return

        self._record_rate_limit()

        wait = self._rate_limiter.seconds_until_available()

        raise RateLimitExceededError(
            "Limite local atingido. Aguarde "
            f"{wait}s antes da próxima requisição."
        )

    def _record_error(self, detail: str) -> None:
        if self._metrics is not None:
            self._metrics.record_error(detail)

    def _record_rate_limit(self) -> None:
        if self._metrics is not None:
            self._metrics.record_rate_limit()
