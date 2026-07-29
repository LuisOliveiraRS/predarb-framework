from __future__ import annotations

import asyncio
from collections.abc import Mapping
from typing import Any

import httpx

from app.core.settings import settings


class HttpClient:
    """
    Cliente HTTP assíncrono e independente
    de event loop.

    Uma nova instância de AsyncClient é criada
    para cada requisição. Isso evita reutilizar
    conexões vinculadas a loops encerrados por
    chamadas repetidas de asyncio.run().
    """

    RETRYABLE_STATUS_CODES = {
        408,
        425,
        429,
        500,
        502,
        503,
        504,
    }

    def __init__(
        self,
        *,
        timeout: float = 10.0,
        max_retries: int = 2,
        retry_delay: float = 0.25,
    ) -> None:
        if timeout <= 0:
            raise ValueError(
                "O timeout HTTP deve ser maior que zero."
            )

        if max_retries < 0:
            raise ValueError(
                "max_retries não pode ser negativo."
            )

        if retry_delay < 0:
            raise ValueError(
                "retry_delay não pode ser negativo."
            )

        self.timeout = float(timeout)
        self.max_retries = int(max_retries)
        self.retry_delay = float(retry_delay)

    async def _sleep_before_retry(
        self,
        attempt: int,
    ) -> None:
        """
        Aplica um backoff linear simples.
        """

        delay = self.retry_delay * (
            attempt + 1
        )

        if delay > 0:
            await asyncio.sleep(delay)

    async def request(
        self,
        method: str,
        url: str,
        *,
        payload: Any = None,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Executa uma requisição HTTP e retorna JSON.
        """

        if not isinstance(method, str):
            raise TypeError(
                "O método HTTP deve ser uma string."
            )

        normalized_method = method.strip().upper()

        if not normalized_method:
            raise ValueError(
                "O método HTTP não pode ser vazio."
            )

        if not isinstance(url, str):
            raise TypeError(
                "A URL deve ser uma string."
            )

        normalized_url = url.strip()

        if not normalized_url:
            raise ValueError(
                "A URL não pode ser vazia."
            )

        request_headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": (
                f"{settings.APP_NAME}/"
                f"{settings.APP_VERSION}"
            ),
        }

        if headers:
            request_headers.update(
                dict(headers)
            )

        last_error: Exception | None = None

        for attempt in range(
            self.max_retries + 1
        ):
            try:
                async with httpx.AsyncClient(
                    timeout=self.timeout,
                    follow_redirects=True,
                ) as client:
                    response = await client.request(
                        method=normalized_method,
                        url=normalized_url,
                        params=params,
                        json=payload,
                        headers=request_headers,
                    )

                if (
                    response.status_code
                    in self.RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                ):
                    await self._sleep_before_retry(
                        attempt,
                    )
                    continue

                response.raise_for_status()

                try:
                    return response.json()

                except ValueError as exc:
                    raise RuntimeError(
                        "A resposta HTTP não contém "
                        "um JSON válido."
                    ) from exc

            except httpx.HTTPStatusError as exc:
                last_error = exc

                status_code = (
                    exc.response.status_code
                )

                if (
                    status_code
                    in self.RETRYABLE_STATUS_CODES
                    and attempt < self.max_retries
                ):
                    await self._sleep_before_retry(
                        attempt,
                    )
                    continue

                raise

            except (
                httpx.TimeoutException,
                httpx.TransportError,
            ) as exc:
                last_error = exc

                if attempt < self.max_retries:
                    await self._sleep_before_retry(
                        attempt,
                    )
                    continue

                raise

        if last_error is not None:
            raise last_error

        raise RuntimeError(
            "A requisição HTTP não foi executada."
        )

    async def get(
        self,
        url: str,
        *,
        params: Mapping[str, Any] | None = None,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Executa uma requisição GET.
        """

        return await self.request(
            "GET",
            url,
            params=params,
            headers=headers,
        )

    async def post(
        self,
        url: str,
        payload: Any = None,
        *,
        headers: Mapping[str, str] | None = None,
    ) -> Any:
        """
        Executa uma requisição POST.
        """

        return await self.request(
            "POST",
            url,
            payload=payload,
            headers=headers,
        )

    async def close(self) -> None:
        """
        Mantido para compatibilidade.

        Não existe cliente persistente para fechar.
        """

        return None


http_client = HttpClient(
    timeout=settings.HYPERLIQUID_TIMEOUT_SECONDS,
    max_retries=settings.HYPERLIQUID_MAX_RETRIES,
    retry_delay=(
        settings.HYPERLIQUID_RETRY_DELAY_SECONDS
    ),
)