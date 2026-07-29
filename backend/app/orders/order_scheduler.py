from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from threading import RLock, Timer
from typing import Any
from uuid import uuid4

from app.orders.order_queue import OrderQueue, order_queue


@dataclass(slots=True)
class ScheduledOrder:
    order: Any
    delay: float = 0.0
    priority: float = 100.0
    allow_duplicate: bool = False
    schedule_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "SCHEDULED"
    created_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    scheduled_for: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    enqueued_at: datetime | None = None
    cancelled_at: datetime | None = None
    timer: Timer | None = field(default=None, repr=False)

    @property
    def order_id(self) -> str:
        return str(getattr(self.order, "id", "") or "").strip()

    def to_dict(self) -> dict[str, Any]:
        return {
            "schedule_id": self.schedule_id,
            "order_id": self.order_id,
            "status": self.status,
            "delay": self.delay,
            "priority": self.priority,
            "allow_duplicate": self.allow_duplicate,
            "created_at": self.created_at.isoformat(),
            "scheduled_for": self.scheduled_for.isoformat(),
            "enqueued_at": self.enqueued_at.isoformat() if self.enqueued_at else None,
            "cancelled_at": (
                self.cancelled_at.isoformat() if self.cancelled_at else None
            ),
        }


class OrderScheduler:
    """Agenda a entrada de ordens na fila pendente do OMS.

    A fila de ordens continua separada da ``ExecutionQueue`` dos workers. O
    agendador não despacha conectores e não altera o estado das ordens.
    """

    def __init__(self, queue: OrderQueue | Any | None = None) -> None:
        self.queue = queue if queue is not None else order_queue
        self._entries: dict[str, ScheduledOrder] = {}
        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(orders: Any) -> list[Any]:
        if orders is None:
            return []
        if isinstance(orders, Mapping):
            return [orders]
        if isinstance(orders, (str, bytes)):
            raise TypeError("orders deve ser uma ordem ou coleção de ordens.")
        if isinstance(orders, Iterable):
            return list(orders)
        return [orders]

    def _enqueue(self, entry: ScheduledOrder) -> None:
        with self._lock:
            if entry.status == "CANCELLED":
                return

        push = getattr(self.queue, "enqueue", None) or getattr(self.queue, "push", None)
        if not callable(push):
            raise TypeError("A fila configurada não possui enqueue() ou push().")

        try:
            push(
                entry.order,
                priority=entry.priority,
                allow_duplicate=entry.allow_duplicate,
            )
        except TypeError:
            try:
                push(entry.order, allow_duplicate=entry.allow_duplicate)
            except TypeError:
                push(entry.order)

        with self._lock:
            entry.status = "ENQUEUED"
            entry.enqueued_at = datetime.now(timezone.utc)
            entry.timer = None

    def schedule_one(
        self,
        order: Any,
        *,
        delay: float = 0.0,
        priority: float = 100,
        allow_duplicate: bool = False,
    ) -> ScheduledOrder:
        if order is None:
            raise ValueError("order não pode ser None.")
        resolved_delay = float(delay)
        if resolved_delay < 0:
            raise ValueError("delay não pode ser negativo.")

        now = datetime.now(timezone.utc)
        entry = ScheduledOrder(
            order=order,
            delay=resolved_delay,
            priority=float(priority),
            allow_duplicate=bool(allow_duplicate),
            scheduled_for=now + timedelta(seconds=resolved_delay),
        )
        with self._lock:
            self._entries[entry.schedule_id] = entry

        if resolved_delay == 0:
            self._enqueue(entry)
        else:
            timer = Timer(resolved_delay, self._enqueue, args=(entry,))
            timer.daemon = True
            entry.timer = timer
            timer.start()
        return entry

    def schedule(
        self,
        orders: Any,
        *,
        delay: float = 0.0,
        priority: float = 100,
        allow_duplicate: bool = False,
    ) -> bool:
        """Interface legada: agenda todas as ordens e retorna ``True``."""

        items = self._as_list(orders)
        entries = [
            self.schedule_one(
                order,
                delay=delay,
                priority=priority,
                allow_duplicate=allow_duplicate,
            )
            for order in items
        ]
        self.last_report = {
            "scheduled": len(entries),
            "delay": float(delay),
            "priority": float(priority),
            "schedule_ids": [entry.schedule_id for entry in entries],
        }
        return True

    schedule_many = schedule

    def cancel(
        self,
        schedule_id: str,
        *,
        remove_enqueued: bool = False,
    ) -> bool:
        with self._lock:
            entry = self._entries.get(str(schedule_id))
            if entry is None or entry.status == "CANCELLED":
                return False
            if entry.timer is not None:
                entry.timer.cancel()
                entry.timer = None
            was_enqueued = entry.status == "ENQUEUED"
            entry.status = "CANCELLED"
            entry.cancelled_at = datetime.now(timezone.utc)

        if was_enqueued and remove_enqueued:
            remove = getattr(self.queue, "remove", None)
            if callable(remove):
                remove(entry.order)
        return True

    def get(self, schedule_id: str) -> ScheduledOrder | None:
        with self._lock:
            return self._entries.get(str(schedule_id))

    def all(self) -> list[ScheduledOrder]:
        with self._lock:
            return list(self._entries.values())

    def pending(self) -> list[ScheduledOrder]:
        with self._lock:
            return [
                entry for entry in self._entries.values() if entry.status == "SCHEDULED"
            ]

    def clear(self, *, remove_enqueued: bool = False) -> int:
        entries = self.all()
        count = 0
        for entry in entries:
            if entry.status != "CANCELLED":
                count += int(
                    self.cancel(
                        entry.schedule_id,
                        remove_enqueued=remove_enqueued,
                    )
                )
        with self._lock:
            self._entries.clear()
        return count

    stop = clear

    def status(self) -> dict[str, Any]:
        entries = self.all()
        counts: dict[str, int] = {}
        for entry in entries:
            counts[entry.status] = counts.get(entry.status, 0) + 1
        return {
            "entries": len(entries),
            "statuses": counts,
            "queue_size": (
                self.queue.size() if callable(getattr(self.queue, "size", None)) else None
            ),
            "last_report": dict(self.last_report),
        }


order_scheduler = OrderScheduler()
