"""Coletor periódico do scanner CEX-CEX.

Espelha a forma da Fase 17, que está validada em produção há um
dia: single-flight entre threads, snapshot em memória, estado
observável e configuração desligada por default.

Repetir uma forma provada é melhor do que inventar outra. As
diferenças em relação ao coletor da Fase 17 são de domínio, não
de arquitetura.

Fail-closed em todos os níveis: venue que falha não derruba o
ciclo, apenas some do conjunto e fica registrada; venue com book
stale é descartada pelo scanner; taxa desconhecida invalida a
rota. Um ciclo sem venue alguma produz relatório vazio com o
motivo, nunca um resultado otimista.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from threading import Lock, RLock
from typing import Any

from app.crypto_arbitrage.domain.errors import (
    CryptoArbitrageError,
)
from app.crypto_arbitrage.domain.models import (
    OrderBookSnapshot,
)
from app.crypto_arbitrage.domain.symbols import SymbolPair
from app.crypto_arbitrage.opportunities.cex_cex import (
    CexCexScanner,
    ScanReport,
)


SAFETY_FLAGS: dict[str, bool] = {
    "market_data_only": True,
    "read_only": True,
    "automatic_execution_authorized": False,
    "execution_authorized": False,
    "financial_execution": False,
    "order_submission_available": False,
    "wallet_signing": False,
    "private_key_access": False,
}


class CryptoScannerService:
    """Executa ciclos de varredura e guarda o último resultado."""

    def __init__(
        self,
        *,
        scanner: CexCexScanner,
        sources: dict[str, Any],
        pair: SymbolPair,
        quantity: str,
        enabled: bool = False,
    ) -> None:
        self.scanner = scanner
        self.sources = dict(sources)
        self.pair = pair
        self.quantity = quantity
        self.enabled = bool(enabled)

        self._cycle_lock = Lock()
        self._state_lock = RLock()

        self._snapshot: ScanReport | None = None
        self._snapshot_at: datetime | None = None

        self._state: dict[str, Any] = {
            "cycles": 0,
            "successes": 0,
            "failures": 0,
            "skipped": 0,
            "last_started_at": None,
            "last_completed_at": None,
            "last_error": None,
            "last_status": "IDLE",
            "last_venues_collected": 0,
            "last_opportunities": 0,
            "last_venue_errors": {},
        }

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    async def collect_books(
        self,
        *,
        now: datetime | None = None,
    ) -> tuple[dict[str, OrderBookSnapshot], dict[str, str]]:
        """Busca os books em paralelo, tolerando falha parcial.

        Uma venue fora do ar não pode impedir a comparação entre
        as demais. O erro é preservado por venue, porque "o
        scanner não achou nada" e "a OKX está fora" pedem ações
        diferentes.
        """

        reference = now or self._now()

        async def fetch(venue_id: str, source: Any):
            try:
                snapshot = await source.fetch_snapshot(
                    self.pair,
                    received_timestamp=reference,
                )

                return (venue_id, snapshot, None)
            except (
                CryptoArbitrageError,
                Exception,
            ) as exc:
                return (venue_id, None, str(exc))

        results = await asyncio.gather(
            *(
                fetch(venue_id, source)
                for venue_id, source in (
                    self.sources.items()
                )
            )
        )

        books: dict[str, OrderBookSnapshot] = {}
        errors: dict[str, str] = {}

        for venue_id, snapshot, error in results:
            if snapshot is not None:
                books[venue_id] = snapshot
                continue

            errors[venue_id] = error or "erro desconhecido"

        return (books, errors)

    async def run_cycle_async(self) -> dict[str, Any]:
        """Um ciclo completo: coleta, varre e guarda."""

        started_at = self._now()

        with self._state_lock:
            self._state["cycles"] += 1
            self._state["last_started_at"] = (
                started_at.isoformat()
            )
            self._state["last_status"] = "RUNNING"

        try:
            books, errors = await self.collect_books(
                now=started_at,
            )

            report = self.scanner.scan(
                pair=self.pair,
                quantity=self.quantity,
                books=books,
                now=started_at,
            )
        except Exception as exc:
            with self._state_lock:
                self._state["failures"] += 1
                self._state["last_error"] = str(exc)
                self._state["last_status"] = "ERROR"
                self._state["last_completed_at"] = (
                    self._now().isoformat()
                )

            return self.status()

        with self._state_lock:
            self._snapshot = report
            self._snapshot_at = started_at

            self._state["successes"] += 1
            self._state["last_error"] = None
            self._state["last_venue_errors"] = errors
            self._state["last_venues_collected"] = len(
                books
            )
            self._state["last_opportunities"] = len(
                report.opportunities
            )
            self._state["last_completed_at"] = (
                self._now().isoformat()
            )
            self._state["last_status"] = (
                "READY" if books else "NO_BOOKS"
            )

        return self.status()

    def run_task(self) -> dict[str, Any]:
        """Adaptador síncrono para o APScheduler.

        O single-flight usa `Lock` de thread, não `asyncio.Lock`:
        o BackgroundScheduler roda o job em thread própria, e a
        seção 28 proíbe compartilhar lock de asyncio entre loops.
        """

        if not self.enabled:
            with self._state_lock:
                self._state["skipped"] += 1
                self._state["last_status"] = "DISABLED"

            return self.status()

        if not self._cycle_lock.acquire(blocking=False):
            with self._state_lock:
                self._state["skipped"] += 1
                self._state["last_status"] = (
                    "SKIPPED_OVERLAP"
                )

            return self.status()

        try:
            return asyncio.run(self.run_cycle_async())
        finally:
            self._cycle_lock.release()

    def snapshot(self) -> dict[str, Any]:
        """Último relatório, sem disparar coleta.

        Ler não coleta. Foi a lição da Fase 17: coleta por acesso
        deixa a carga upstream proporcional ao tráfego do
        dashboard, e não ao intervalo configurado.
        """

        with self._state_lock:
            report = self._snapshot
            snapshot_at = self._snapshot_at

        if report is None:
            return {
                "status": "WARMING_UP",
                "snapshot_available": False,
                "detail": (
                    "Nenhum ciclo concluído desde o "
                    "último reinício."
                ),
                **SAFETY_FLAGS,
            }

        payload = report.to_dict()
        payload["status"] = "READY"
        payload["snapshot_available"] = True
        payload["served_from_snapshot"] = True
        payload["snapshot_at"] = (
            snapshot_at.isoformat()
            if snapshot_at is not None
            else None
        )
        payload.update(SAFETY_FLAGS)

        return payload

    def status(self) -> dict[str, Any]:
        with self._state_lock:
            state = dict(self._state)

        state.update(
            {
                "enabled": self.enabled,
                "pair": self.pair.canonical,
                "quantity": str(self.quantity),
                "venues": sorted(self.sources),
                "snapshot_available": (
                    self._snapshot is not None
                ),
                "scanner": self.scanner.status(),
            }
        )

        state.update(SAFETY_FLAGS)

        return state
