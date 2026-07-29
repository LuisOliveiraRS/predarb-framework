from __future__ import annotations

import inspect
import logging
from threading import RLock
from typing import Any, Callable

from app.events.event_bus import event_bus


logger = logging.getLogger(__name__)


class KernelEvents:
    """
    Fachada oficial do Kernel para o EventBus.

    Responsabilidades:

    - publicar eventos;
    - registrar handlers;
    - remover handlers quando suportado;
    - contabilizar publicações;
    - contabilizar erros;
    - preservar compatibilidade com eventos
      síncronos e assíncronos.

    Este componente não cria um novo EventBus.
    Ele utiliza a instância oficial disponível
    em app.events.event_bus.
    """

    def __init__(self) -> None:
        self._lock = RLock()

        self._published_events = 0
        self._failed_events = 0
        self._subscriptions = 0

    def _record_success(self) -> None:
        with self._lock:
            self._published_events += 1

    def _record_failure(self) -> None:
        with self._lock:
            self._failed_events += 1

    def _record_subscription(self) -> None:
        with self._lock:
            self._subscriptions += 1

    async def _await_publication(
        self,
        awaitable: Any,
    ) -> Any:
        """
        Aguarda uma publicação assíncrona
        e registra seu resultado.
        """

        try:
            result = await awaitable

        except Exception:
            self._record_failure()

            logger.exception(
                "Erro durante publicação "
                "assíncrona de evento."
            )

            raise

        self._record_success()

        return result

    def publish(
        self,
        event: Any,
    ) -> Any:
        """
        Publica um evento no EventBus oficial.

        Quando o EventBus retornar uma coroutine,
        o resultado também deverá ser aguardado:

            await kernel_events.publish(event)

        Para uso explicitamente assíncrono, também
        existe o método publish_async().
        """

        if event is None:
            raise ValueError(
                "Não é possível publicar "
                "um evento None."
            )

        try:
            result = event_bus.publish(
                event,
            )

        except Exception:
            self._record_failure()

            logger.exception(
                "Erro ao publicar evento."
            )

            raise

        if inspect.isawaitable(result):
            return self._await_publication(
                result,
            )

        self._record_success()

        return result

    async def publish_async(
        self,
        event: Any,
    ) -> Any:
        """
        Publica um evento e garante que qualquer
        resultado assíncrono seja aguardado.
        """

        result = self.publish(
            event,
        )

        if inspect.isawaitable(result):
            return await result

        return result

    def subscribe(
        self,
        event_name: str,
        handler: Callable[..., Any],
    ) -> Any:
        """
        Registra um handler no EventBus oficial.
        """

        if not isinstance(event_name, str):
            raise TypeError(
                "O nome do evento deve ser "
                "uma string."
            )

        normalized_name = event_name.strip()

        if not normalized_name:
            raise ValueError(
                "O nome do evento não pode "
                "ser vazio."
            )

        if not callable(handler):
            raise TypeError(
                "O handler do evento deve "
                "ser executável."
            )

        result = event_bus.subscribe(
            normalized_name,
            handler,
        )

        if result is not False:
            self._record_subscription()

        return result

    def unsubscribe(
        self,
        event_name: str,
        handler: Callable[..., Any],
    ) -> Any:
        """
        Remove um handler quando o EventBus
        implementar unsubscribe().

        Retorna False caso a implementação atual
        ainda não forneça essa operação.
        """

        method = getattr(
            event_bus,
            "unsubscribe",
            None,
        )

        if not callable(method):
            return False

        return method(
            event_name,
            handler,
        )

    def statistics(self) -> dict[str, int]:
        """
        Retorna as métricas da fachada de eventos.
        """

        with self._lock:
            return {
                "published": (
                    self._published_events
                ),
                "failed": (
                    self._failed_events
                ),
                "subscriptions": (
                    self._subscriptions
                ),
            }

    def reset_statistics(self) -> None:
        """
        Reinicia as métricas da fachada.
        """

        with self._lock:
            self._published_events = 0
            self._failed_events = 0
            self._subscriptions = 0

    emit = publish


kernel_events = KernelEvents()