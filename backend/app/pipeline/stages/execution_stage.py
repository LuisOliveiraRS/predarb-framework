from __future__ import annotations

import inspect
from collections.abc import Mapping
from datetime import datetime, timezone
from typing import Any, Callable

from app.pipeline.pipeline_stage import PipelineStage


class ExecutionStage(PipelineStage):
    """
    Adaptador opcional entre o Pipeline e um executor.

    A execução real permanece desabilitada por padrão.
    Para ativá-la, é obrigatório injetar um executor e
    criar o estágio com enabled=True.

    O executor pode ser:

    - um objeto com método execute(order, venue);
    - uma função compatível com esse contrato.
    """

    def __init__(
        self,
        *,
        executor: Any = None,
        enabled: bool = False,
        venue_resolver: (
            Callable[
                [Any, Any],
                Any,
            ]
            | None
        ) = None,
        fail_fast: bool = True,
    ) -> None:
        self.executor = executor

        self.enabled = bool(
            enabled
        )

        self.venue_resolver = (
            venue_resolver
        )

        self.fail_fast = bool(
            fail_fast
        )

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(
            target,
            Mapping,
        ):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @staticmethod
    def _executor_callable(
        executor: Any,
    ) -> Callable[..., Any]:
        if callable(
            executor
        ):
            return executor

        method = getattr(
            executor,
            "execute",
            None,
        )

        if callable(
            method
        ):
            return method

        raise TypeError(
            "O executor deve ser uma função "
            "ou possuir execute()."
        )

    def _resolve_venue(
        self,
        order: Any,
        context: Any,
    ) -> Any:
        if self.venue_resolver is not None:
            return self.venue_resolver(
                order,
                context,
            )

        venue = self._read_field(
            order,
            "venue",
            None,
        )

        if venue is not None:
            return venue

        return context.venue

    @staticmethod
    def _invoke(
        callable_executor: (
            Callable[..., Any]
        ),
        order: Any,
        venue: Any,
    ) -> Any:
        try:
            signature = inspect.signature(
                callable_executor
            )

        except (
            TypeError,
            ValueError,
        ):
            signature = None

        if signature is not None:
            parameters = list(
                signature.parameters.values()
            )

            accepts_varargs = any(
                parameter.kind
                == inspect.Parameter.VAR_POSITIONAL
                for parameter in parameters
            )

            positional_parameters = [
                parameter
                for parameter in parameters
                if parameter.kind
                in {
                    (
                        inspect.Parameter
                        .POSITIONAL_ONLY
                    ),
                    (
                        inspect.Parameter
                        .POSITIONAL_OR_KEYWORD
                    ),
                }
            ]

            if (
                accepts_varargs
                or len(
                    positional_parameters
                )
                >= 2
            ):
                result = (
                    callable_executor(
                        order,
                        venue,
                    )
                )

            else:
                result = (
                    callable_executor(
                        order
                    )
                )

        else:
            result = callable_executor(
                order,
                venue,
            )

        if inspect.isawaitable(
            result
        ):
            raise TypeError(
                "O executor retornou uma "
                "coroutine. O Pipeline atual "
                "é síncrono."
            )

        return result

    @classmethod
    def _serialize_report(
        cls,
        report: Any,
    ) -> Any:
        if report is None:
            return None

        if isinstance(
            report,
            Mapping,
        ):
            return dict(
                report
            )

        to_dict = getattr(
            report,
            "to_dict",
            None,
        )

        if callable(
            to_dict
        ):
            return to_dict()

        return report

    def process(
        self,
        context: Any,
    ) -> Any:
        orders = list(
            context.orders
            or []
        )

        if not self.enabled:
            context.metadata[
                "live_execution"
            ] = {
                "enabled": False,
                "status": "DISABLED",
                "orders_available": len(
                    orders
                ),
            }

            return context

        if self.executor is None:
            raise RuntimeError(
                "A execução real foi ativada "
                "sem um executor."
            )

        callable_executor = (
            self._executor_callable(
                self.executor
            )
        )

        reports: list[Any] = []

        failures: list[
            dict[str, Any]
        ] = []

        for index, order in enumerate(
            orders
        ):
            venue = self._resolve_venue(
                order,
                context,
            )

            try:
                raw_report = self._invoke(
                    callable_executor,
                    order,
                    venue,
                )

                reports.append(
                    self._serialize_report(
                        raw_report
                    )
                )

            except Exception as exc:
                failures.append(
                    {
                        "index": index,
                        "order_id": (
                            self._read_field(
                                order,
                                "id",
                                None,
                            )
                        ),
                        "error": str(exc),
                    }
                )

                if self.fail_fast:
                    raise

        summary = {
            "mode": "LIVE",
            "status": (
                "SUCCESS"
                if reports
                and not failures
                else "PARTIAL"
                if reports
                else "EMPTY"
                if not failures
                else "FAILED"
            ),
            "orders_received": len(
                orders
            ),
            "orders_executed": len(
                reports
            ),
            "orders_failed": len(
                failures
            ),
            "reports": reports,
            "failures": failures,
            "completed_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

        context.execution_reports = (
            reports
        )

        context.execution_report = (
            summary
        )

        context.metadata[
            "live_execution"
        ] = {
            "enabled": True,
            "status": summary["status"],
            "orders_received": len(
                orders
            ),
            "orders_executed": len(
                reports
            ),
            "orders_failed": len(
                failures
            ),
        }

        return context

    execute = process