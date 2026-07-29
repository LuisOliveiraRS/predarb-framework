from __future__ import annotations

import heapq

from dataclasses import dataclass, field
from datetime import datetime, timezone
from itertools import count
from math import isfinite
from threading import Condition, RLock
from time import monotonic
from typing import Any


class ExecutionQueueClosed(RuntimeError):
    """Indica tentativa de inserção em uma fila encerrada."""


@dataclass(order=True, slots=True)
class _QueueEntry:
    priority: float
    sequence: int
    queued_at: datetime = field(compare=False)
    item: Any = field(compare=False)
    key: str = field(compare=False)


class ExecutionQueue:
    """Fila de prioridade estável e thread-safe para tarefas de execução.

    Menores valores de ``priority`` são processados primeiro. O contador de
    sequência impede que dois itens com a mesma prioridade precisem ser
    comparáveis entre si, corrigindo a limitação do ``PriorityQueue`` antigo.
    """

    def __init__(self) -> None:
        self._heap: list[_QueueEntry] = []
        self._keys: dict[str, int] = {}
        self._sequence = count()
        self._lock = RLock()
        self._condition = Condition(self._lock)
        self._unfinished_tasks = 0
        self._closed = False

        # Alias legado para código que apenas inspeciona o atributo.
        self.queue = self._heap

    @staticmethod
    def _priority(value: Any) -> float:
        if isinstance(value, bool):
            raise TypeError("priority não pode ser booleano.")
        try:
            priority = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError("priority deve ser numérico.") from exc
        if not isfinite(priority):
            raise ValueError("priority deve ser finito.")
        return priority

    @staticmethod
    def _key(item: Any, explicit: str | None = None) -> str:
        if explicit is not None:
            resolved = str(explicit).strip()
            if not resolved:
                raise ValueError("key não pode ser vazia.")
            return resolved

        for field_name in ("task_id", "id", "order_id"):
            value = getattr(item, field_name, None)
            if value not in (None, ""):
                return f"{field_name}:{value}"
        return f"object:{id(item)}"

    def push(
        self,
        item: Any,
        priority: Any = 100,
        *,
        allow_duplicate: bool = True,
        key: str | None = None,
    ) -> Any:
        if item is None:
            raise ValueError("item não pode ser None.")

        resolved_priority = self._priority(priority)
        resolved_key = self._key(item, key)

        with self._condition:
            if self._closed:
                raise ExecutionQueueClosed("A fila de execução está encerrada.")
            if not allow_duplicate and self._keys.get(resolved_key, 0) > 0:
                return item

            entry = _QueueEntry(
                priority=resolved_priority,
                sequence=next(self._sequence),
                queued_at=datetime.now(timezone.utc),
                item=item,
                key=resolved_key,
            )
            heapq.heappush(self._heap, entry)
            self._keys[resolved_key] = self._keys.get(resolved_key, 0) + 1
            self._unfinished_tasks += 1
            self._condition.notify()

        return item

    enqueue = push
    put = push

    def pop(
        self,
        block: bool = False,
        timeout: float | None = None,
    ) -> Any | None:
        if timeout is not None:
            timeout = float(timeout)
            if timeout < 0:
                raise ValueError("timeout não pode ser negativo.")

        with self._condition:
            if not block:
                if not self._heap:
                    return None
            else:
                deadline = None if timeout is None else monotonic() + timeout
                while not self._heap:
                    if self._closed:
                        return None
                    if deadline is None:
                        self._condition.wait()
                    else:
                        remaining = deadline - monotonic()
                        if remaining <= 0:
                            return None
                        self._condition.wait(remaining)

            entry = heapq.heappop(self._heap)
            count_for_key = self._keys.get(entry.key, 0)
            if count_for_key <= 1:
                self._keys.pop(entry.key, None)
            else:
                self._keys[entry.key] = count_for_key - 1
            return entry.item

    dequeue = pop
    get = pop

    def task_done(self) -> None:
        with self._condition:
            if self._unfinished_tasks <= 0:
                raise ValueError("task_done() chamado mais vezes que push().")
            self._unfinished_tasks -= 1
            if self._unfinished_tasks == 0:
                self._condition.notify_all()

    def join(self, timeout: float | None = None) -> bool:
        if timeout is not None:
            timeout = float(timeout)
            if timeout < 0:
                raise ValueError("timeout não pode ser negativo.")

        with self._condition:
            deadline = None if timeout is None else monotonic() + timeout
            while self._unfinished_tasks:
                if deadline is None:
                    self._condition.wait()
                else:
                    remaining = deadline - monotonic()
                    if remaining <= 0:
                        return False
                    self._condition.wait(remaining)
            return True

    def peek(self) -> Any | None:
        with self._lock:
            return self._heap[0].item if self._heap else None

    def contains(self, item_or_key: Any) -> bool:
        candidate = str(item_or_key or "").strip()
        possible_keys = {candidate}
        if candidate:
            possible_keys.update(
                {
                    f"task_id:{candidate}",
                    f"id:{candidate}",
                    f"order_id:{candidate}",
                }
            )
        try:
            possible_keys.add(self._key(item_or_key))
        except Exception:
            pass
        with self._lock:
            return any(self._keys.get(key, 0) > 0 for key in possible_keys)

    def remove(self, item_or_key: Any) -> Any | None:
        candidate = str(item_or_key or "").strip()
        possible_keys = {candidate}
        if candidate:
            possible_keys.update(
                {
                    f"task_id:{candidate}",
                    f"id:{candidate}",
                    f"order_id:{candidate}",
                }
            )
        try:
            possible_keys.add(self._key(item_or_key))
        except Exception:
            pass

        with self._condition:
            for index, entry in enumerate(self._heap):
                if entry.key not in possible_keys and entry.item is not item_or_key:
                    continue
                removed = self._heap.pop(index)
                heapq.heapify(self._heap)
                count_for_key = self._keys.get(removed.key, 0)
                if count_for_key <= 1:
                    self._keys.pop(removed.key, None)
                else:
                    self._keys[removed.key] = count_for_key - 1
                self._unfinished_tasks = max(0, self._unfinished_tasks - 1)
                if self._unfinished_tasks == 0:
                    self._condition.notify_all()
                return removed.item
        return None

    def all(self) -> list[Any]:
        with self._lock:
            return [entry.item for entry in sorted(self._heap)]

    list = all

    def clear(self) -> int:
        with self._condition:
            removed = len(self._heap)
            self._heap.clear()
            self._keys.clear()
            self._unfinished_tasks = max(0, self._unfinished_tasks - removed)
            if self._unfinished_tasks == 0:
                self._condition.notify_all()
            return removed

    def close(self, *, discard: bool = False) -> None:
        with self._condition:
            self._closed = True
            if discard:
                self.clear()
            self._condition.notify_all()

    def reopen(self) -> None:
        with self._condition:
            self._closed = False
            self._condition.notify_all()

    def wake(self) -> None:
        with self._condition:
            self._condition.notify_all()

    def size(self) -> int:
        with self._lock:
            return len(self._heap)

    count = size

    def empty(self) -> bool:
        return self.size() == 0

    @property
    def unfinished_tasks(self) -> int:
        with self._lock:
            return self._unfinished_tasks

    @property
    def closed(self) -> bool:
        with self._lock:
            return self._closed

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "size": len(self._heap),
                "unfinished_tasks": self._unfinished_tasks,
                "closed": self._closed,
            }

    def __len__(self) -> int:
        return self.size()

    def __bool__(self) -> bool:
        return not self.empty()


execution_queue = ExecutionQueue()
