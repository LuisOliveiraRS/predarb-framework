from __future__ import annotations

import inspect

from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable


class RollbackEngine:
    """Registra rollback e só executa compensação quando habilitado explicitamente."""

    def __init__(self, *, enabled: bool = False, action: Any = None) -> None:
        self.enabled = bool(enabled)
        self.action = action
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _callable(action: Any) -> Callable[..., Any]:
        if callable(action):
            return action
        method = getattr(action, "execute", None)
        if callable(method):
            return method
        raise TypeError("A ação de rollback deve ser chamável ou possuir execute().")

    @staticmethod
    def _invoke(operation: Callable[..., Any], context: Any, reason: str) -> Any:
        try:
            signature = inspect.signature(operation)
        except (TypeError, ValueError):
            signature = None

        if signature is None:
            result = operation(context, reason)
        else:
            positional = [
                parameter
                for parameter in signature.parameters.values()
                if parameter.kind
                in {
                    inspect.Parameter.POSITIONAL_ONLY,
                    inspect.Parameter.POSITIONAL_OR_KEYWORD,
                }
            ]
            varargs = any(
                parameter.kind == inspect.Parameter.VAR_POSITIONAL
                for parameter in signature.parameters.values()
            )
            if varargs or len(positional) >= 2:
                result = operation(context, reason)
            elif len(positional) == 1:
                result = operation(context)
            else:
                result = operation()

        if inspect.isawaitable(result):
            raise TypeError("Rollback assíncrono não é suportado pelo fluxo síncrono.")
        return result

    @staticmethod
    def _mark_context(context: Any, report: Mapping[str, Any]) -> None:
        mark = getattr(context, "mark_rollback", None)
        if callable(mark):
            mark(True)
        else:
            setattr(context, "rollback", True)

        metadata = getattr(context, "metadata", None)
        if isinstance(metadata, dict):
            metadata["rollback"] = dict(report)

    def configure(self, *, enabled: bool | None = None, action: Any = None) -> None:
        if enabled is not None:
            self.enabled = bool(enabled)
        if action is not None:
            self.action = action

    def execute(
        self,
        context: Any,
        *,
        reason: str = "ROLLBACK_REQUIRED",
        action: Any = None,
        enabled: bool | None = None,
    ) -> dict[str, Any]:
        if context is None:
            raise ValueError("context não pode ser None.")

        resolved_enabled = self.enabled if enabled is None else bool(enabled)
        resolved_action = action or self.action
        base = {
            "required": True,
            "attempted": False,
            "success": False,
            "status": "REQUIRED",
            "reason": str(reason or "ROLLBACK_REQUIRED").strip(),
            "order_id": str(getattr(context, "order_id", "") or ""),
            "venue": str(getattr(context, "venue_name", "") or ""),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "result": None,
            "error": None,
        }

        if not resolved_enabled:
            base["status"] = "DISABLED"
            base["reason"] = "ROLLBACK_EXECUTION_DISABLED"
            self._mark_context(context, base)
            self.last_report = dict(base)
            return dict(base)

        if resolved_action is None:
            base["status"] = "PENDING_ACTION"
            base["reason"] = "ROLLBACK_ACTION_MISSING"
            self._mark_context(context, base)
            self.last_report = dict(base)
            return dict(base)

        base["attempted"] = True
        try:
            result = self._invoke(self._callable(resolved_action), context, base["reason"])
        except Exception as exc:
            base["status"] = "FAILED"
            base["error"] = str(exc)
        else:
            base["status"] = "SUCCESS"
            base["success"] = True
            base["result"] = result

        self._mark_context(context, base)
        self.last_report = dict(base)
        return dict(base)

    mark = execute

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "action_configured": self.action is not None,
            "last_report": dict(self.last_report),
        }


rollback_engine = RollbackEngine()
