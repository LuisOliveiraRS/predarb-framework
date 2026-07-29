from __future__ import annotations

import inspect

from collections.abc import Mapping
from copy import deepcopy
from enum import Enum
from math import isfinite
from typing import Any, Callable

from app.trading.execution_context import ExecutionContext
from app.trading.execution_logger import TradingExecutionLogger, execution_logger
from app.trading.execution_metrics import ExecutionMetrics, execution_metrics
from app.trading.execution_result import ExecutionResult
from app.trading.latency_monitor import LatencyMonitor, latency_monitor
from app.trading.retry_policy import RetryPolicy, retry_policy
from app.trading.rollback_engine import RollbackEngine, rollback_engine
from app.trading.slippage_guard import SlippageGuard, slippage_guard
from app.trading.trade_manager import TradeManager, trade_manager


_SUCCESS_STATUSES = {
    "SUCCESS",
    "OK",
    "ACCEPTED",
    "ACKNOWLEDGED",
    "SUBMITTED",
    "OPEN",
    "PARTIALLY_FILLED",
    "FILLED",
    "COMPLETED",
}

_FAILURE_STATUSES = {
    "FAILED",
    "ERROR",
    "REJECTED",
    "CANCELLED",
    "CANCELED",
    "EXPIRED",
    "DISABLED",
}

_EXECUTED_STATUSES = {
    "PARTIALLY_FILLED",
    "FILLED",
    "COMPLETED",
}


class ExecutionPipeline:
    """Fluxo síncrono e protegido da camada Trading.

    O pipeline coordena observabilidade, retry, slippage, rollback e criação de
    ``Trade``. A execução real permanece desabilitada por padrão e só ocorre
    quando ``enabled=True`` e um executor explícito é fornecido.
    """

    def __init__(
        self,
        *,
        executor: Any = None,
        enabled: bool = False,
        latency: LatencyMonitor | None = None,
        slippage: SlippageGuard | None = None,
        retry: RetryPolicy | None = None,
        rollback: RollbackEngine | None = None,
        metrics: ExecutionMetrics | None = None,
        logger: TradingExecutionLogger | None = None,
        trades: TradeManager | None = None,
    ) -> None:
        self.executor = executor
        self.enabled = bool(enabled)
        self.latency = latency or latency_monitor
        self.slippage = slippage or slippage_guard
        self.retry = retry or retry_policy
        self.rollback = rollback or rollback_engine
        self.metrics = metrics or execution_metrics
        self.logger = logger or execution_logger
        self.trades = trades or trade_manager
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field_name: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field_name, default)
        if target is None:
            return default
        return getattr(target, field_name, default)

    @staticmethod
    def _text(value: Any, default: str = "") -> str:
        if isinstance(value, Enum):
            value = value.value
        return str(default if value is None else value).strip()

    @staticmethod
    def _number(value: Any) -> float | None:
        if value is None or isinstance(value, bool):
            return None
        try:
            number = float(value)
        except (TypeError, ValueError):
            return None
        return number if isfinite(number) else None

    @classmethod
    def _first(cls, target: Any, names: tuple[str, ...]) -> Any:
        for name in names:
            value = cls._read(target, name, None)
            if value is not None:
                return value
        return None

    @classmethod
    def _first_number(cls, target: Any, names: tuple[str, ...]) -> float | None:
        return cls._number(cls._first(target, names))

    @classmethod
    def _status(cls, report: Any, *, default: str = "UNKNOWN") -> str:
        status = cls._first(report, ("status", "state"))
        return cls._text(status, default).upper() or default

    @classmethod
    def _success(cls, report: Any) -> bool:
        explicit = cls._first(report, ("success", "ok", "accepted"))
        if explicit is not None:
            return bool(explicit)
        status = cls._status(report)
        if status in _FAILURE_STATUSES:
            return False
        return status in _SUCCESS_STATUSES

    @classmethod
    def _error(cls, report: Any) -> str | None:
        value = cls._first(report, ("error", "reason", "message", "detail"))
        return None if value in (None, "") else str(value)

    @staticmethod
    def _callable(executor: Any) -> Callable[..., Any]:
        if callable(executor):
            return executor
        method = getattr(executor, "execute", None)
        if callable(method):
            return method
        raise TypeError("O executor deve ser chamável ou possuir execute().")

    @staticmethod
    def _invoke(operation: Callable[..., Any], context: ExecutionContext) -> Any:
        try:
            signature = inspect.signature(operation)
        except (TypeError, ValueError):
            signature = None

        if signature is None:
            result = operation(context.order, context.venue)
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

            if varargs or len(positional) >= 3:
                result = operation(context.order, context.venue, context)
            elif len(positional) == 2:
                result = operation(context.order, context.venue)
            elif len(positional) == 1:
                parameter_name = positional[0].name.strip().lower()
                if parameter_name in {"context", "ctx", "execution_context"}:
                    result = operation(context)
                else:
                    result = operation(context.order)
            else:
                result = operation()

        if inspect.isawaitable(result):
            raise TypeError("Executor assíncrono não é suportado pelo fluxo síncrono.")
        return result

    @classmethod
    def _normalize_report(cls, raw: Any, context: ExecutionContext) -> dict[str, Any]:
        if raw is None:
            return {
                "status": "FAILED",
                "success": False,
                "executed": False,
                "error": "EXECUTION_REPORT_MISSING",
                "order_id": context.order_id,
                "platform": context.venue_name,
                "raw": None,
            }

        if isinstance(raw, Mapping):
            source = dict(raw)
        else:
            to_dict = getattr(raw, "to_dict", None)
            source = to_dict() if callable(to_dict) else {}

        status = cls._status(raw, default=cls._status(source, default="UNKNOWN"))
        success = cls._success(raw) if status != "UNKNOWN" else cls._success(source)
        quantity = cls._first_number(
            raw,
            ("executed_quantity", "applied_quantity", "filled_quantity", "quantity"),
        )
        if quantity is None:
            quantity = cls._first_number(
                source,
                ("executed_quantity", "applied_quantity", "filled_quantity", "quantity"),
            )
        price = cls._first_number(
            raw,
            ("average_price", "executed_price", "fill_price", "price"),
        )
        if price is None:
            price = cls._first_number(
                source,
                ("average_price", "executed_price", "fill_price", "price"),
            )
        fee = cls._first_number(raw, ("fee", "fees", "fees_paid"))
        if fee is None:
            fee = cls._first_number(source, ("fee", "fees", "fees_paid"))

        executed = bool(
            (quantity is not None and quantity > 0)
            or status in _EXECUTED_STATUSES
            or cls._read(raw, "executed", False)
            or cls._read(source, "executed", False)
        )

        return {
            **source,
            "status": status,
            "success": bool(success),
            "executed": executed,
            "order_id": str(source.get("order_id") or context.order_id),
            "platform": str(
                source.get("platform")
                or source.get("venue")
                or context.venue_name
                or getattr(context.order, "platform", "")
            ),
            "executed_quantity": 0.0 if quantity is None else max(0.0, quantity),
            "average_price": 0.0 if price is None else max(0.0, price),
            "fee": 0.0 if fee is None else max(0.0, fee),
            "error": cls._error(raw) or cls._error(source),
            "raw": raw,
        }

    @classmethod
    def _expected_price(cls, context: ExecutionContext, override: Any = None) -> float | None:
        explicit = cls._number(override)
        if explicit is not None and explicit > 0:
            return explicit
        order_price = cls._number(getattr(context.order, "price", None))
        return order_price if order_price is not None and order_price > 0 else None

    @classmethod
    def _side(cls, context: ExecutionContext) -> str:
        return cls._text(getattr(context.order, "side", "BUY"), "BUY").upper()

    @classmethod
    def _quantity(cls, context: ExecutionContext, report: Mapping[str, Any]) -> float:
        report_quantity = cls._number(report.get("executed_quantity"))
        if report_quantity is not None and report_quantity > 0:
            return report_quantity
        order_quantity = cls._number(getattr(context.order, "quantity", 0.0))
        return max(0.0, order_quantity or 0.0)

    @staticmethod
    def _copy_report(report: Mapping[str, Any]) -> dict[str, Any]:
        try:
            return deepcopy(dict(report))
        except Exception:
            return dict(report)

    def configure(
        self,
        *,
        executor: Any = None,
        enabled: bool | None = None,
    ) -> None:
        if executor is not None:
            self.executor = executor
        if enabled is not None:
            self.enabled = bool(enabled)

    def disable(self) -> None:
        self.enabled = False

    def _finalize(
        self,
        *,
        context: ExecutionContext,
        result: ExecutionResult,
        started: float,
        create_trade: bool,
        include_failed_trade: bool,
    ) -> ExecutionResult:
        self.latency.stop(started, label="trading_execution", context=context)

        latency_report = dict(context.metadata.get("latency", {}))
        result.metadata.setdefault("latency", latency_report)
        result.metadata.setdefault("retries", context.retries)
        result.metadata.setdefault("rollback", context.rollback)

        report = result.report if isinstance(result.report, Mapping) else {}
        actual_execution = bool(report.get("executed", False))
        trade = None
        if create_trade and actual_execution:
            trade = self.trades.create_from_result(
                result,
                include_failed=include_failed_trade or not result.success,
                metadata={
                    "source": "trading_execution_pipeline",
                    "latency": latency_report,
                    "slippage": context.metadata.get("slippage"),
                    "rollback": context.metadata.get("rollback"),
                },
            )
            result.trade = trade

        context.finish(
            success=result.success,
            report=result.report,
            result={
                "success": result.success,
                "status": result.status,
                "error": result.error,
            },
            trade=trade,
            error=result.error,
        )

        if result.status != "DISABLED":
            self.metrics.record(result)
        self.logger.execution(result, context=context)

        self.last_report = {
            "status": result.status,
            "success": result.success,
            "order_id": context.order_id,
            "venue": context.venue_name,
            "executed": actual_execution,
            "trade_created": trade is not None,
            "retries": context.retries,
            "rollback": context.rollback,
            "latency_ms": latency_report.get("milliseconds", context.duration_ms),
            "error": result.error,
        }
        return result

    def execute(
        self,
        context: ExecutionContext,
        *,
        executor: Any = None,
        enabled: bool | None = None,
        expected_price: Any = None,
        max_slippage: Any = None,
        retry_on_report_failure: bool = False,
        rollback_on_failure: bool = False,
        rollback_action: Any = None,
        rollback_enabled: bool | None = None,
        create_trade: bool = True,
        include_failed_trade: bool = True,
    ) -> ExecutionResult:
        if not isinstance(context, ExecutionContext):
            raise TypeError("context deve ser uma instância de ExecutionContext.")
        if context.finished:
            return ExecutionResult.failure(
                "CONTEXT_ALREADY_FINISHED",
                context=context,
                status="REJECTED",
            )

        started = self.latency.start()
        resolved_enabled = (
            context.live_enabled
            if enabled is None and context.live_enabled
            else self.enabled if enabled is None else bool(enabled)
        )
        context.live_enabled = bool(resolved_enabled)

        self.logger.info(
            "Execução Trading iniciada",
            event="EXECUTION_STARTED",
            context=context,
            metadata={"live_enabled": resolved_enabled},
        )

        if not resolved_enabled:
            report = {
                "status": "DISABLED",
                "success": False,
                "executed": False,
                "reason": "LIVE_EXECUTION_DISABLED",
                "order_id": context.order_id,
                "platform": context.venue_name,
            }
            result = ExecutionResult.failure(
                "LIVE_EXECUTION_DISABLED",
                report=report,
                context=context,
                status="DISABLED",
                metadata={"live_enabled": False},
            )
            return self._finalize(
                context=context,
                result=result,
                started=started,
                create_trade=False,
                include_failed_trade=False,
            )

        resolved_executor = executor or self.executor
        if resolved_executor is None:
            result = ExecutionResult.failure(
                "TRADING_EXECUTOR_MISSING",
                report={
                    "status": "FAILED",
                    "success": False,
                    "executed": False,
                    "error": "TRADING_EXECUTOR_MISSING",
                    "order_id": context.order_id,
                },
                context=context,
                status="FAILED",
            )
            return self._finalize(
                context=context,
                result=result,
                started=started,
                create_trade=False,
                include_failed_trade=False,
            )

        operation = self._callable(resolved_executor)
        normalized_report: dict[str, Any] | None = None

        while True:
            try:
                raw_report = self._invoke(operation, context)
                normalized_report = self._normalize_report(raw_report, context)
            except Exception as exc:
                decision = self.retry.register(context, exc)
                if decision.allowed:
                    self.logger.warning(
                        "Falha temporária; nova tentativa autorizada",
                        event="EXECUTION_RETRY",
                        context=context,
                        error=exc,
                        metadata=decision.to_dict(),
                    )
                    continue

                rollback_report = None
                if rollback_on_failure:
                    rollback_report = self.rollback.execute(
                        context,
                        reason="EXECUTION_EXCEPTION",
                        action=rollback_action,
                        enabled=rollback_enabled,
                    )

                result = ExecutionResult.failure(
                    exc,
                    report={
                        "status": "FAILED",
                        "success": False,
                        "executed": False,
                        "error": str(exc),
                        "order_id": context.order_id,
                        "rollback": rollback_report,
                    },
                    context=context,
                    status="FAILED",
                    metadata={
                        "retry": decision.to_dict(),
                        "rollback": rollback_report,
                    },
                )
                return self._finalize(
                    context=context,
                    result=result,
                    started=started,
                    create_trade=False,
                    include_failed_trade=False,
                )

            if normalized_report["success"]:
                break

            if retry_on_report_failure:
                report_error = RuntimeError(
                    normalized_report.get("error")
                    or normalized_report.get("status")
                    or "EXECUTION_REPORT_FAILED"
                )
                decision = self.retry.register(context, report_error)
                if decision.allowed:
                    self.logger.warning(
                        "Relatório de falha; nova tentativa autorizada",
                        event="EXECUTION_RETRY",
                        context=context,
                        error=report_error,
                        metadata=decision.to_dict(),
                    )
                    continue

            rollback_report = None
            if rollback_on_failure:
                rollback_report = self.rollback.execute(
                    context,
                    reason="EXECUTION_REPORT_FAILED",
                    action=rollback_action,
                    enabled=rollback_enabled,
                )
                normalized_report["rollback"] = rollback_report

            result = ExecutionResult.failure(
                normalized_report.get("error")
                or normalized_report.get("status")
                or "EXECUTION_FAILED",
                report=self._copy_report(normalized_report),
                context=context,
                status=normalized_report.get("status", "FAILED"),
                metadata={"rollback": rollback_report},
            )
            return self._finalize(
                context=context,
                result=result,
                started=started,
                create_trade=create_trade,
                include_failed_trade=include_failed_trade,
            )

        expected = self._expected_price(context, expected_price)
        executed_price = self._number(normalized_report.get("average_price"))
        slippage_report = None
        if expected is not None and executed_price is not None and executed_price > 0:
            slippage_report = self.slippage.evaluate(
                expected,
                executed_price,
                side=self._side(context),
                quantity=self._quantity(context, normalized_report),
                max_slippage=max_slippage,
                context=context,
            )
            normalized_report["slippage"] = slippage_report
            normalized_report["slippage_rate"] = slippage_report["adverse_rate"]

            if not slippage_report["within_limit"]:
                normalized_report["success"] = False
                normalized_report["status"] = "SLIPPAGE_REJECTED"
                normalized_report["error"] = "SLIPPAGE_LIMIT_EXCEEDED"

                rollback_report = None
                if rollback_on_failure:
                    rollback_report = self.rollback.execute(
                        context,
                        reason="SLIPPAGE_LIMIT_EXCEEDED",
                        action=rollback_action,
                        enabled=rollback_enabled,
                    )
                    normalized_report["rollback"] = rollback_report

                result = ExecutionResult.failure(
                    "SLIPPAGE_LIMIT_EXCEEDED",
                    report=self._copy_report(normalized_report),
                    context=context,
                    status="SLIPPAGE_REJECTED",
                    metadata={
                        "slippage": slippage_report,
                        "rollback": rollback_report,
                    },
                )
                return self._finalize(
                    context=context,
                    result=result,
                    started=started,
                    create_trade=create_trade,
                    include_failed_trade=True,
                )

        result = ExecutionResult.ok(
            report=self._copy_report(normalized_report),
            context=context,
            status=normalized_report.get("status", "SUCCESS"),
            metadata={
                "slippage": slippage_report,
                "live_enabled": True,
            },
        )
        return self._finalize(
            context=context,
            result=result,
            started=started,
            create_trade=create_trade,
            include_failed_trade=include_failed_trade,
        )

    run = execute

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "executor_configured": self.executor is not None,
            "metrics": self.metrics.stats(),
            "rollback": self.rollback.status(),
            "last_report": dict(self.last_report),
        }


execution_pipeline = ExecutionPipeline()
