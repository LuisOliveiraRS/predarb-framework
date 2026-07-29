from __future__ import annotations

import random
import time

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from threading import RLock
from time import perf_counter
from typing import Any


@dataclass(slots=True)
class RetryResult:
    """Resultado estruturado de uma operação com tentativas controladas."""

    success: bool
    value: Any = None
    error: Exception | None = None
    attempts: int = 0
    max_attempts: int = 0
    delays: list[float] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    elapsed: float = 0.0
    started_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )
    completed_at: datetime = field(
        default_factory=lambda: datetime.now(timezone.utc)
    )

    def raise_for_error(self) -> "RetryResult":
        if not self.success and self.error is not None:
            raise self.error
        return self

    def to_dict(self) -> dict[str, Any]:
        return {
            "success": self.success,
            "attempts": self.attempts,
            "max_attempts": self.max_attempts,
            "delays": list(self.delays),
            "errors": list(self.errors),
            "elapsed": round(self.elapsed, 8),
            "error": str(self.error) if self.error is not None else None,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat(),
        }


class RetryEngine:
    """Executa funções com limite de tentativas e backoff controlado.

    A assinatura legada continua válida::

        retry_engine.execute(func, *args, **kwargs)

    Opções específicas do mecanismo são fornecidas em ``retry_options`` para
    que não colidam com argumentos da função executada.
    """

    def __init__(
        self,
        max_attempts: int = 3,
        delay: float = 0.5,
        *,
        backoff_factor: float = 2.0,
        max_delay: float = 30.0,
        jitter: float = 0.0,
        retry_exceptions: tuple[type[Exception], ...] = (Exception,),
        sleep: Callable[[float], Any] = time.sleep,
    ) -> None:
        self.max_attempts = self._positive_int(max_attempts, "max_attempts")
        self.delay = self._non_negative_number(delay, "delay")
        self.backoff_factor = self._positive_number(
            backoff_factor,
            "backoff_factor",
        )
        self.max_delay = self._non_negative_number(max_delay, "max_delay")
        self.jitter = self._non_negative_number(jitter, "jitter")
        self.retry_exceptions = self._exception_types(retry_exceptions)
        self.sleep = sleep

        self._lock = RLock()
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _positive_int(value: Any, field_name: str) -> int:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        try:
            number = int(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser inteiro.") from exc
        if number <= 0:
            raise ValueError(f"{field_name} deve ser maior que zero.")
        return number

    @staticmethod
    def _non_negative_number(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser numérico.") from exc
        if not isfinite(number) or number < 0:
            raise ValueError(f"{field_name} deve ser finito e não negativo.")
        return number

    @classmethod
    def _positive_number(cls, value: Any, field_name: str) -> float:
        number = cls._non_negative_number(value, field_name)
        if number <= 0:
            raise ValueError(f"{field_name} deve ser maior que zero.")
        return number

    @staticmethod
    def _exception_types(
        value: Any,
    ) -> tuple[type[Exception], ...]:
        if isinstance(value, type) and issubclass(value, Exception):
            return (value,)
        try:
            resolved = tuple(value)
        except TypeError as exc:
            raise TypeError("retry_exceptions deve conter tipos de Exception.") from exc
        if not resolved or any(
            not isinstance(item, type) or not issubclass(item, Exception)
            for item in resolved
        ):
            raise TypeError("retry_exceptions deve conter tipos de Exception.")
        return resolved

    def _resolve_options(
        self,
        retry_options: Mapping[str, Any] | None,
    ) -> dict[str, Any]:
        options = dict(retry_options or {})
        return {
            "max_attempts": self._positive_int(
                options.get("max_attempts", self.max_attempts),
                "max_attempts",
            ),
            "delay": self._non_negative_number(
                options.get("delay", self.delay),
                "delay",
            ),
            "backoff_factor": self._positive_number(
                options.get("backoff_factor", self.backoff_factor),
                "backoff_factor",
            ),
            "max_delay": self._non_negative_number(
                options.get("max_delay", self.max_delay),
                "max_delay",
            ),
            "jitter": self._non_negative_number(
                options.get("jitter", self.jitter),
                "jitter",
            ),
            "retry_exceptions": self._exception_types(
                options.get("retry_exceptions", self.retry_exceptions)
            ),
            "retry_if": options.get("retry_if"),
            "on_retry": options.get("on_retry"),
            "sleep": options.get("sleep", self.sleep),
        }

    @staticmethod
    def _should_retry(
        error: Exception,
        attempt: int,
        *,
        retry_exceptions: tuple[type[Exception], ...],
        retry_if: Callable[[Exception, int], bool] | None,
    ) -> bool:
        if not isinstance(error, retry_exceptions):
            return False
        if retry_if is None:
            return True
        return bool(retry_if(error, attempt))

    @staticmethod
    def _delay_for(
        retry_index: int,
        *,
        delay: float,
        backoff_factor: float,
        max_delay: float,
        jitter: float,
    ) -> float:
        base = min(max_delay, delay * (backoff_factor ** retry_index))
        if jitter > 0:
            base += random.uniform(0.0, jitter)
        return max(0.0, min(max_delay + jitter, base))

    def run(
        self,
        func: Callable[..., Any],
        *args: Any,
        retry_options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> RetryResult:
        if not callable(func):
            raise TypeError("func deve ser chamável.")

        options = self._resolve_options(retry_options)
        max_attempts = options["max_attempts"]
        started_at = datetime.now(timezone.utc)
        started = perf_counter()
        errors: list[str] = []
        delays: list[float] = []
        final_error: Exception | None = None
        value: Any = None
        success = False
        attempts = 0

        for attempt in range(1, max_attempts + 1):
            attempts = attempt
            try:
                value = func(*args, **kwargs)
                success = True
                final_error = None
                break
            except Exception as exc:
                final_error = exc
                errors.append(str(exc))

                can_retry = (
                    attempt < max_attempts
                    and self._should_retry(
                        exc,
                        attempt,
                        retry_exceptions=options["retry_exceptions"],
                        retry_if=options["retry_if"],
                    )
                )
                if not can_retry:
                    break

                retry_delay = self._delay_for(
                    attempt - 1,
                    delay=options["delay"],
                    backoff_factor=options["backoff_factor"],
                    max_delay=options["max_delay"],
                    jitter=options["jitter"],
                )
                delays.append(retry_delay)

                on_retry = options["on_retry"]
                if callable(on_retry):
                    on_retry(
                        exc,
                        attempt,
                        retry_delay,
                    )

                if retry_delay > 0:
                    sleeper = options["sleep"]
                    if not callable(sleeper):
                        raise TypeError("sleep deve ser chamável.")
                    sleeper(retry_delay)

        result = RetryResult(
            success=success,
            value=value,
            error=final_error,
            attempts=attempts,
            max_attempts=max_attempts,
            delays=delays,
            errors=errors,
            elapsed=perf_counter() - started,
            started_at=started_at,
            completed_at=datetime.now(timezone.utc),
        )

        with self._lock:
            self.last_report = result.to_dict()

        return result

    def execute(
        self,
        func: Callable[..., Any],
        *args: Any,
        retry_options: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> Any:
        """Executa e retorna o valor, relançando o último erro em falha."""

        result = self.run(
            func,
            *args,
            retry_options=retry_options,
            **kwargs,
        )
        result.raise_for_error()
        return result.value

    retry = execute

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "max_attempts": self.max_attempts,
                "delay": self.delay,
                "backoff_factor": self.backoff_factor,
                "max_delay": self.max_delay,
                "jitter": self.jitter,
                "last_report": dict(self.last_report),
            }


retry_engine = RetryEngine()
