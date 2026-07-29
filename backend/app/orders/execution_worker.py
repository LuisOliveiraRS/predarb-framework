from __future__ import annotations

import threading

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from threading import Event, RLock, Thread
from typing import Any, Callable, Mapping
from uuid import uuid4

from app.orders.execution_logger import ExecutionLogger, execution_logger
from app.orders.execution_queue import ExecutionQueue, execution_queue
from app.orders.retry_engine import RetryEngine, retry_engine


def _serialize(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, BaseException):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _serialize(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_serialize(item) for item in value]
    to_dict = getattr(value, "to_dict", None)
    if callable(to_dict):
        try:
            return _serialize(to_dict())
        except Exception:
            pass
    return str(value)


@dataclass(slots=True)
class ExecutionTask:
    fn: Callable[..., Any]
    args: tuple[Any, ...] = field(default_factory=tuple)
    kwargs: dict[str, Any] = field(default_factory=dict)
    priority: float = 100.0
    retry_options: dict[str, Any] = field(default_factory=dict)
    task_id: str = field(default_factory=lambda: str(uuid4()))
    status: str = "QUEUED"
    result: Any = None
    error: Exception | None = None
    attempts: int = 0
    submitted_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    started_at: datetime | None = None
    completed_at: datetime | None = None
    _completed: Event = field(default_factory=Event, repr=False)

    @property
    def done(self) -> bool:
        return self._completed.is_set()

    @property
    def successful(self) -> bool:
        return self.status == "SUCCESS"

    def wait(self, timeout: float | None = None) -> bool:
        return self._completed.wait(timeout)

    def get_result(self, timeout: float | None = None) -> Any:
        if not self.wait(timeout):
            raise TimeoutError(f"A tarefa {self.task_id} não terminou no prazo.")
        if self.error is not None:
            raise self.error
        return self.result

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "status": self.status,
            "priority": self.priority,
            "attempts": self.attempts,
            "successful": self.successful,
            "done": self.done,
            "result": _serialize(self.result),
            "error": str(self.error) if self.error is not None else None,
            "submitted_at": self.submitted_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": (
                self.completed_at.isoformat() if self.completed_at else None
            ),
        }


class ExecutionWorker:
    """Pool de workers com fila compartilhada e desligamento seguro."""

    def __init__(
        self,
        *,
        queue: ExecutionQueue | None = None,
        retry: RetryEngine | None = None,
        logger: ExecutionLogger | None = None,
        workers: int = 1,
        poll_interval: float = 0.1,
        name: str = "ExecutionWorker",
    ) -> None:
        if isinstance(workers, bool) or int(workers) <= 0:
            raise ValueError("workers deve ser maior que zero.")
        if float(poll_interval) <= 0:
            raise ValueError("poll_interval deve ser maior que zero.")

        self.queue = queue if queue is not None else execution_queue
        self.retry_engine = retry if retry is not None else retry_engine
        self.logger = logger if logger is not None else execution_logger
        self.workers = int(workers)
        self.poll_interval = float(poll_interval)
        self.name = str(name or "ExecutionWorker")

        self.thread: Thread | None = None
        self.threads: list[Thread] = []
        self.running = False
        self.accepting = True
        self._drain_on_stop = True
        self._stop_event = Event()
        self._lock = RLock()
        self._tasks: dict[str, ExecutionTask] = {}
        self._processed = 0
        self._succeeded = 0
        self._failed = 0

    def submit(
        self,
        fn: Callable[..., Any],
        *args: Any,
        priority: float = 100,
        retry_options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> ExecutionTask:
        if not callable(fn):
            raise TypeError("fn deve ser chamável.")
        with self._lock:
            if not self.accepting:
                raise RuntimeError("O worker não está aceitando novas tarefas.")

        task = ExecutionTask(
            fn=fn,
            args=tuple(args),
            kwargs=dict(kwargs),
            priority=float(priority),
            retry_options=dict(retry_options or {}),
        )
        with self._lock:
            self._tasks[task.task_id] = task
        self.queue.push(
            task,
            priority=task.priority,
            allow_duplicate=False,
            key=f"task:{task.task_id}",
        )
        return task

    def _process(self, task: ExecutionTask) -> None:
        task.status = "RUNNING"
        task.started_at = datetime.now(timezone.utc)

        result = self.retry_engine.run(
            task.fn,
            *task.args,
            retry_options=task.retry_options,
            **task.kwargs,
        )
        task.attempts = result.attempts
        task.completed_at = datetime.now(timezone.utc)

        if result.success:
            task.status = "SUCCESS"
            task.result = result.value
            task.error = None
            with self._lock:
                self._succeeded += 1
        else:
            task.status = "FAILED"
            task.error = result.error
            with self._lock:
                self._failed += 1

        with self._lock:
            self._processed += 1
        task._completed.set()
        self.logger.task(task)

    def _loop(self, index: int) -> None:
        threading.current_thread().name = f"{self.name}-{index + 1}"

        while True:
            if self._stop_event.is_set():
                if not self._drain_on_stop or self.queue.empty():
                    break

            item = self.queue.pop(
                block=True,
                timeout=self.poll_interval,
            )
            if item is None:
                continue

            try:
                if not isinstance(item, ExecutionTask):
                    raise TypeError(
                        "ExecutionWorker recebeu um item que não é ExecutionTask."
                    )
                self._process(item)
            except Exception as exc:
                if isinstance(item, ExecutionTask):
                    item.status = "FAILED"
                    item.error = exc
                    item.completed_at = datetime.now(timezone.utc)
                    item._completed.set()
                    with self._lock:
                        self._processed += 1
                        self._failed += 1
                self.logger.exception(
                    "Falha interna no ExecutionWorker.",
                    error=exc,
                )
            finally:
                self.queue.task_done()

        with self._lock:
            if not any(thread.is_alive() for thread in self.threads if thread is not threading.current_thread()):
                self.running = False

    def start(self) -> bool:
        with self._lock:
            if self.running:
                return False
            self.queue.reopen()
            self._stop_event.clear()
            self._drain_on_stop = True
            self.accepting = True
            self.running = True
            self.threads = [
                Thread(
                    target=self._loop,
                    args=(index,),
                    daemon=True,
                    name=f"{self.name}-{index + 1}",
                )
                for index in range(self.workers)
            ]
            self.thread = self.threads[0]
            threads = list(self.threads)

        for thread in threads:
            thread.start()
        return True

    def stop(
        self,
        *,
        wait: bool = True,
        drain: bool = True,
        timeout: float = 5.0,
    ) -> bool:
        with self._lock:
            if not self.running:
                self.accepting = False
                return True
            self.accepting = False
            self._drain_on_stop = bool(drain)
            self._stop_event.set()
            threads = list(self.threads)

        if not drain:
            pending = self.queue.all()
            self.queue.clear()
            for item in pending:
                if isinstance(item, ExecutionTask) and not item.done:
                    item.status = "CANCELLED"
                    item.completed_at = datetime.now(timezone.utc)
                    item._completed.set()

        self.queue.wake()
        if wait:
            deadline = None if timeout is None else max(0.0, float(timeout))
            for thread in threads:
                thread.join(deadline)

        alive = any(thread.is_alive() for thread in threads)
        with self._lock:
            self.running = alive
        return not alive

    def get_task(self, task_id: str) -> ExecutionTask | None:
        with self._lock:
            return self._tasks.get(str(task_id))

    def tasks(self) -> list[ExecutionTask]:
        with self._lock:
            return list(self._tasks.values())

    def clear_completed(self) -> int:
        with self._lock:
            completed_ids = [
                task_id for task_id, task in self._tasks.items() if task.done
            ]
            for task_id in completed_ids:
                self._tasks.pop(task_id, None)
            return len(completed_ids)

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "running": self.running,
                "accepting": self.accepting,
                "workers": self.workers,
                "threads_alive": sum(thread.is_alive() for thread in self.threads),
                "queued": self.queue.size(),
                "unfinished_tasks": self.queue.unfinished_tasks,
                "tasks": len(self._tasks),
                "processed": self._processed,
                "succeeded": self._succeeded,
                "failed": self._failed,
            }


execution_worker = ExecutionWorker()
