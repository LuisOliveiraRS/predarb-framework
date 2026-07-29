from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Any


@dataclass(frozen=True, slots=True)
class RetryDecision:
    allowed: bool
    retries: int
    max_retries: int
    remaining: int
    delay: float
    reason: str
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "allowed": self.allowed,
            "retries": self.retries,
            "max_retries": self.max_retries,
            "remaining": self.remaining,
            "delay": self.delay,
            "reason": self.reason,
            "error": self.error,
        }


class RetryPolicy:
    """Decide retries e backoff; não dorme e não reenvia ordens."""

    MAX_RETRIES = 2

    def __init__(
        self,
        *,
        max_retries: int = MAX_RETRIES,
        delay: float = 0.25,
        backoff_factor: float = 2.0,
        max_delay: float = 5.0,
        retry_exceptions: tuple[type[BaseException], ...] = (Exception,),
    ) -> None:
        if isinstance(max_retries, bool):
            raise TypeError("max_retries não pode ser booleano.")
        self.max_retries = int(max_retries)
        if self.max_retries < 0:
            raise ValueError("max_retries não pode ser negativo.")

        self.delay = self._non_negative(delay, "delay")
        self.backoff_factor = self._non_negative(backoff_factor, "backoff_factor")
        self.max_delay = self._non_negative(max_delay, "max_delay")
        if not retry_exceptions:
            raise ValueError("retry_exceptions não pode ser vazio.")
        self.retry_exceptions = tuple(retry_exceptions)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _non_negative(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser numérico.") from exc
        if not isfinite(number) or number < 0:
            raise ValueError(f"{field_name} deve ser finito e não negativo.")
        return number

    @staticmethod
    def _retries(context: Any) -> int:
        value = getattr(context, "retries", 0)
        if isinstance(value, bool):
            return 0
        try:
            retries = int(value)
        except (TypeError, ValueError):
            return 0
        return max(0, retries)

    def backoff(self, retries: int) -> float:
        if retries <= 0 or self.delay == 0:
            return 0.0
        exponent = max(0, retries - 1)
        value = self.delay * (self.backoff_factor ** exponent)
        return round(min(value, self.max_delay), 6)

    def evaluate(self, context: Any, error: BaseException | None = None) -> RetryDecision:
        retries = self._retries(context)
        finished = bool(getattr(context, "finished", False))
        rollback = bool(getattr(context, "rollback", False))

        if finished:
            reason = "CONTEXT_FINISHED"
            allowed = False
        elif rollback:
            reason = "ROLLBACK_ACTIVE"
            allowed = False
        elif error is not None and not isinstance(error, self.retry_exceptions):
            reason = "NON_RETRYABLE_ERROR"
            allowed = False
        elif retries >= self.max_retries:
            reason = "RETRY_LIMIT_REACHED"
            allowed = False
        else:
            reason = "RETRY_ALLOWED"
            allowed = True

        next_retry_number = retries + 1
        decision = RetryDecision(
            allowed=allowed,
            retries=retries,
            max_retries=self.max_retries,
            remaining=max(0, self.max_retries - retries),
            delay=self.backoff(next_retry_number) if allowed else 0.0,
            reason=reason,
            error=None if error is None else str(error),
        )
        self.last_report = decision.to_dict()
        return decision

    def allow(self, context: Any, error: BaseException | None = None) -> bool:
        return self.evaluate(context, error).allowed

    def register(self, context: Any, error: BaseException | None = None) -> RetryDecision:
        decision = self.evaluate(context, error)
        if not decision.allowed:
            return decision

        increment = getattr(context, "increment_retry", None)
        if callable(increment):
            increment()
        else:
            setattr(context, "retries", decision.retries + 1)

        metadata = getattr(context, "metadata", None)
        if isinstance(metadata, dict):
            history = metadata.setdefault("retry_history", [])
            if isinstance(history, list):
                history.append(decision.to_dict())

        return decision


retry_policy = RetryPolicy()
