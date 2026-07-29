from __future__ import annotations

import logging
from collections.abc import Mapping
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.events.event_bus import event_bus


logger = logging.getLogger(__name__)


class MarketListener:
    """
    Listener de acompanhamento das atualizações
    de mercados.

    Este componente não persiste mercados.

    A persistência é responsabilidade exclusiva de:

        ConnectorManager
            ↓
        MarketRepository

    O MarketListener registra métricas e mantém
    informações sobre a última sincronização.
    """

    EVENT_NAME = "market.updated"

    def __init__(self) -> None:
        self._lock = RLock()

        self._subscribed = False
        self._active = False

        self._last_update: datetime | None = None
        self._last_market_count = 0
        self._updates_processed = 0
        self._invalid_events = 0
        self._last_status: str | None = None
        self._last_connectors: dict[str, Any] = {}

    @property
    def running(self) -> bool:
        with self._lock:
            return self._active

    def start(self) -> bool:
        """
        Inicia o listener de forma idempotente.
        """

        with self._lock:
            if self._active:
                return False

            if not self._subscribed:
                event_bus.subscribe(
                    self.EVENT_NAME,
                    self.handle_market_update,
                )

                self._subscribed = True

            self._active = True

        logger.info(
            "MarketListener iniciado."
        )

        return True

    def stop(self) -> bool:
        """
        Desativa o processamento de eventos.
        """

        with self._lock:
            if not self._active:
                return False

            self._active = False

        logger.info(
            "MarketListener encerrado."
        )

        return True

    def _record_invalid_event(
        self,
        reason: str,
    ) -> None:
        with self._lock:
            self._invalid_events += 1

        logger.warning(
            "Evento market.updated ignorado: %s",
            reason,
        )

    def handle_market_update(
        self,
        event: Any,
    ) -> None:
        """
        Registra uma atualização concluída.
        """

        with self._lock:
            if not self._active:
                return

        payload = getattr(
            event,
            "payload",
            None,
        )

        if not isinstance(payload, Mapping):
            self._record_invalid_event(
                "payload ausente ou inválido.",
            )
            return

        markets = payload.get(
            "markets",
            [],
        )

        if markets is None:
            markets = []

        if isinstance(
            markets,
            (str, bytes, Mapping),
        ):
            self._record_invalid_event(
                "o campo markets não é uma coleção.",
            )
            return

        try:
            market_count = len(
                list(markets)
            )

        except TypeError:
            self._record_invalid_event(
                "o campo markets não é iterável.",
            )
            return

        payload_count = payload.get(
            "count",
            market_count,
        )

        try:
            payload_count = int(
                payload_count
            )

        except (TypeError, ValueError):
            payload_count = market_count

        connector_statuses = payload.get(
            "connectors",
            {},
        )

        if not isinstance(
            connector_statuses,
            Mapping,
        ):
            connector_statuses = {}

        synchronization_status = str(
            payload.get(
                "status",
                "success",
            )
        )

        now = datetime.now(
            timezone.utc,
        )

        with self._lock:
            self._last_update = now
            self._last_market_count = (
                payload_count
            )
            self._updates_processed += 1
            self._last_status = (
                synchronization_status
            )
            self._last_connectors = dict(
                connector_statuses
            )

        logger.info(
            "Atualização de mercados processada: "
            "%s mercados.",
            payload_count,
        )

    def status(self) -> dict[str, Any]:
        """
        Retorna o estado operacional do listener.
        """

        with self._lock:
            return {
                "running": self._active,
                "subscribed": self._subscribed,
                "event_name": self.EVENT_NAME,
                "last_market_count": (
                    self._last_market_count
                ),
                "updates_processed": (
                    self._updates_processed
                ),
                "invalid_events": (
                    self._invalid_events
                ),
                "last_status": self._last_status,
                "last_connectors": dict(
                    self._last_connectors
                ),
                "last_update": (
                    self._last_update.isoformat()
                    if self._last_update
                    else None
                ),
            }


market_listener = MarketListener()