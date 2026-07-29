from __future__ import annotations

import inspect

from collections.abc import (
    Iterable,
    Mapping,
)
from copy import deepcopy
from typing import Any, Callable

from app.execution.execution_plan import (
    ExecutionPlan,
)
from app.execution.execution_policy import (
    ExecutionPolicy,
    execution_policy,
)
from app.execution.execution_report import (
    ExecutionReport,
    execution_report,
)
from app.execution.execution_validator import (
    ExecutionValidator,
    execution_validator,
)


class ExecutionEngine:
    """
    Prepara planos de execução e mantém a
    execução real protegida.

    A execução real somente ocorre quando:

    1. enabled=True;
    2. um executor é injetado explicitamente;
    3. o objeto recebido é uma ordem, não apenas
       um ExecutionPlan.
    """

    def __init__(
        self,
        *,
        validator: (
            ExecutionValidator
            | None
        ) = None,
        policy: (
            ExecutionPolicy
            | None
        ) = None,
        reporter: (
            ExecutionReport
            | None
        ) = None,
        executor: Any = None,
        enabled: bool = False,
    ) -> None:
        self.validator = (
            validator
            or execution_validator
        )

        self.policy = (
            policy
            or execution_policy
        )

        self.reporter = (
            reporter
            or execution_report
        )

        self.executor = executor

        self.enabled = bool(
            enabled
        )

        self.last_report: dict[
            str,
            Any,
        ] = {}

    @staticmethod
    def _as_list(
        opportunities: Any,
    ) -> list[Any]:
        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            Mapping,
        ):
            return [
                opportunities
            ]

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "opportunities deve ser "
                "uma coleção."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(
                opportunities
            )

        return [
            opportunities
        ]

    @staticmethod
    def _attach(
        target: Any,
        key: str,
        value: Any,
    ) -> None:
        if isinstance(
            target,
            dict,
        ):
            target[key] = value

            return

        metadata = getattr(
            target,
            "metadata",
            None,
        )

        if isinstance(
            metadata,
            dict,
        ):
            metadata[key] = value

    @staticmethod
    def _execution_data(
        opportunity: Any,
    ) -> Mapping[str, Any]:
        if isinstance(
            opportunity,
            Mapping,
        ):
            execution = opportunity.get(
                "execution",
                {},
            )

        else:
            metadata = getattr(
                opportunity,
                "metadata",
                {},
            )

            execution = (
                metadata.get(
                    "execution",
                    {},
                )
                if isinstance(
                    metadata,
                    Mapping,
                )
                else {}
            )

        if isinstance(
            execution,
            Mapping,
        ):
            return execution

        return {}

    def create_plan(
        self,
        opportunity: Any,
    ) -> ExecutionPlan:
        policy = self.policy.create(
            opportunity
        )

        return self.validator.build_plan(
            opportunity,
            policy=policy,
        )

    def prepare(
        self,
        opportunities: Any,
        *,
        include_rejected: bool = False,
    ) -> list[Any]:
        """
        Converte oportunidades em planos.

        Por padrão, retorna somente oportunidades
        prontas para criação de ordens.
        """

        items = self._as_list(
            opportunities
        )

        prepared: list[Any] = []

        rejected: list[
            dict[str, Any]
        ] = []

        for index, opportunity in enumerate(
            items
        ):
            result = deepcopy(
                opportunity
            )

            plan = self.create_plan(
                opportunity
            )

            report = self.reporter.create(
                plan
            )

            self._attach(
                result,
                "execution_plan",
                plan.to_dict(),
            )

            self._attach(
                result,
                "execution",
                report,
            )

            if (
                plan.execute
                or include_rejected
            ):
                prepared.append(
                    result
                )

            if not plan.execute:
                rejected.append(
                    {
                        "index": index,
                        "reason": (
                            plan.reason
                        ),
                        "reasons": (
                            plan.metadata[
                                "validation"
                            ]["reasons"]
                        ),
                    }
                )

        approved_count = sum(
            1
            for opportunity in prepared
            if bool(
                self._execution_data(
                    opportunity
                ).get(
                    "approved",
                    False,
                )
            )
        )

        self.last_report = {
            "input": len(items),
            "prepared": approved_count,
            "returned": len(
                prepared
            ),
            "rejected": len(
                rejected
            ),
            "include_rejected": bool(
                include_rejected
            ),
            "details": rejected,
            "live_enabled": (
                self.enabled
            ),
        }

        return prepared

    def configure(
        self,
        *,
        executor: Any = None,
        enabled: bool = False,
    ) -> None:
        """
        Configura explicitamente o executor live.
        """

        self.executor = executor

        self.enabled = bool(
            enabled
        )

    def disable(self) -> None:
        self.enabled = False

    @staticmethod
    def _callable(
        executor: Any,
    ) -> Callable[..., Any]:
        if callable(executor):
            return executor

        method = getattr(
            executor,
            "execute",
            None,
        )

        if callable(method):
            return method

        raise TypeError(
            "O executor deve ser uma função "
            "ou possuir execute()."
        )

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

        if signature is None:
            result = callable_executor(
                order,
                venue,
            )

        else:
            positional = [
                parameter
                for parameter
                in signature.parameters.values()
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

            accepts_varargs = any(
                parameter.kind
                == inspect.Parameter.VAR_POSITIONAL
                for parameter
                in signature.parameters.values()
            )

            if (
                accepts_varargs
                or len(positional) >= 2
            ):
                result = callable_executor(
                    order,
                    venue,
                )

            else:
                result = callable_executor(
                    order
                )

        if inspect.isawaitable(
            result
        ):
            raise TypeError(
                "O executor assíncrono não é "
                "suportado pelo fluxo síncrono."
            )

        return result

    def execute(
        self,
        order: Any,
        venue: Any = None,
        *,
        enabled: bool | None = None,
        executor: Any = None,
    ) -> dict[str, Any]:
        """
        Envia uma ordem somente quando a execução
        live estiver explicitamente habilitada.

        ExecutionPlan não é uma ordem e não pode
        ser encaminhado diretamente ao executor.
        """

        resolved_enabled = (
            self.enabled
            if enabled is None
            else bool(enabled)
        )

        if isinstance(
            order,
            ExecutionPlan,
        ):
            if not order.execute:
                return self.reporter.create(
                    order,
                    status="REJECTED",
                    mode="LIVE",
                )

            raise TypeError(
                "ExecutionPlan não é uma ordem. "
                "Converta o plano em ordens pelo OMS."
            )

        if not resolved_enabled:
            return {
                "status": "DISABLED",
                "mode": "LIVE",
                "executed": False,
                "reason": (
                    "LIVE_EXECUTION_DISABLED"
                ),
            }

        resolved_executor = (
            executor
            or self.executor
        )

        if resolved_executor is None:
            raise RuntimeError(
                "Execução real habilitada sem "
                "executor configurado."
            )

        callable_executor = self._callable(
            resolved_executor
        )

        try:
            result = self._invoke(
                callable_executor,
                order,
                venue,
            )

        except Exception as exc:
            return {
                "status": "FAILED",
                "mode": "LIVE",
                "executed": False,
                "reason": str(exc),
            }

        return {
            "status": "SUCCESS",
            "mode": "LIVE",
            "executed": True,
            "result": result,
        }

    def status(self) -> dict[str, Any]:
        return {
            "enabled": self.enabled,
            "executor_configured": (
                self.executor is not None
            ),
            "last_report": dict(
                self.last_report
            ),
        }


execution_engine = ExecutionEngine()