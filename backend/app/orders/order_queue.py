from __future__ import annotations

from collections import deque
from threading import RLock
from typing import Any


class OrderQueue:
    """Fila FIFO thread-safe de ordens aguardando despacho."""

    def __init__(self) -> None:
        self.queue: deque[Any] = deque()
        self._queued_keys: set[str] = set()
        self._lock = RLock()

    @staticmethod
    def _key(order: Any) -> str:
        order_id = str(getattr(order, "id", "") or "").strip()
        return order_id or f"object:{id(order)}"

    def enqueue(self, order: Any, *, allow_duplicate: bool = False) -> Any:
        if order is None:
            raise ValueError("order não pode ser None.")

        key = self._key(order)
        with self._lock:
            if not allow_duplicate and key in self._queued_keys:
                return order
            self.queue.append(order)
            self._queued_keys.add(key)
        return order

    push = enqueue
    put = enqueue

    def dequeue(self) -> Any | None:
        with self._lock:
            if not self.queue:
                return None
            order = self.queue.popleft()
            key = self._key(order)
            if not any(self._key(item) == key for item in self.queue):
                self._queued_keys.discard(key)
            return order

    pop = dequeue
    get = dequeue

    def peek(self) -> Any | None:
        with self._lock:
            return self.queue[0] if self.queue else None

    def remove(self, order_or_id: Any) -> Any | None:
        target_id = (
            str(getattr(order_or_id, "id", "") or "").strip()
            or str(order_or_id or "").strip()
        )
        if not target_id:
            return None

        with self._lock:
            for index, order in enumerate(self.queue):
                if str(getattr(order, "id", "") or "").strip() == target_id:
                    removed = self.queue[index]
                    del self.queue[index]
                    self._queued_keys.discard(self._key(removed))
                    return removed
        return None

    def contains(self, order_or_id: Any) -> bool:
        target_id = (
            str(getattr(order_or_id, "id", "") or "").strip()
            or str(order_or_id or "").strip()
        )
        if not target_id:
            return False
        with self._lock:
            return any(
                str(getattr(order, "id", "") or "").strip() == target_id
                for order in self.queue
            )

    def size(self) -> int:
        with self._lock:
            return len(self.queue)

    count = size

    def empty(self) -> bool:
        return self.size() == 0

    def clear(self) -> None:
        with self._lock:
            self.queue.clear()
            self._queued_keys.clear()

    def all(self) -> list[Any]:
        with self._lock:
            return list(self.queue)

    list = all

    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return not self.empty()


order_queue = OrderQueue()
