from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.execution.execution_engine import (
    ExecutionEngine,
    execution_engine,
)
from app.execution.execution_plan import (
    ExecutionPlan,
)
from app.execution.execution_report import (
    ExecutionReport,
    execution_report,
)
from app.execution.execution_statistics import (
    ExecutionStatistics,
    execution_statistics,
)


class ExecutionOrchestrator:
    """
    Fachada de alto nível da camada Execution.

    Responsabilidades:

    - preparar oportunidades e planos;
    - registrar relatórios e estatísticas;
    - manter a execução live explícita e separada;
    - não transformar planos em ordens.

    A criação das duas ordens coordenadas pertence
    ao OMS.
    """

    def __init__(
        self,
        *,
        engine: ExecutionEngine | None = None,
        reporter: ExecutionReport | None = None,
        statistics: ExecutionStatistics | None = None,
    ) -> None:
        self.engine = (
            engine
            or execution_engine
        )

        self.reporter = (
            reporter
            or execution_report
        )

        self.statistics = (
            statistics
            or execution_statistics
        )

        self.last_report: dict[
            str,
            Any,
        ] = {}

    @staticmethod
    def _as_list(
        values: Any,
    ) -> list[Any]:
        if values is None:
            return []

        if isinstance(
            values,
            Mapping,
        ):
            return [
                values
            ]

        if isinstance(
            values,
            (str, bytes),
        ):
            raise TypeError(
                "O valor deve ser uma "
                "coleção válida."
            )

        if isinstance(
            values,
            Iterable,
        ):
            return list(
                values
            )

        return [
            values
        ]

    @staticmethod
    def _execution_report(
        opportunity: Any,
    ) -> dict[str, Any]:
        if isinstance(
            opportunity,
            Mapping,
        ):
            report = opportunity.get(
                "execution",
                {},
            )

        else:
            metadata = getattr(
                opportunity,
                "metadata",
                {},
            )

            report = (
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

        return (
            dict(
                report
            )
            if isinstance(
                report,
                Mapping,
            )
            else {}
        )

    @classmethod
    def _approved(
        cls,
        opportunity: Any,
    ) -> bool:
        return bool(
            cls._execution_report(
                opportunity
            ).get(
                "approved",
                False,
            )
        )

    def prepare(
        self,
        opportunities: Any,
        *,
        include_rejected: bool = False,
    ) -> list[Any]:
        """
        Prepara oportunidades e registra todos
        os relatórios, inclusive os rejeitados.
        """

        items = self._as_list(
            opportunities
        )

        prepared_with_rejected = (
            self.engine.prepare(
                items,
                include_rejected=True,
            )
        )

        reports: list[
            dict[str, Any]
        ] = []

        for opportunity in (
            prepared_with_rejected
        ):
            report = self._execution_report(
                opportunity
            )

            if report:
                reports.append(
                    report
                )

                self.statistics.update(
                    report
                )

        approved = [
            opportunity
            for opportunity
            in prepared_with_rejected
            if self._approved(
                opportunity
            )
        ]

        returned = (
            prepared_with_rejected
            if include_rejected
            else approved
        )

        self.last_report = {
            "mode": "PREPARE",
            "input": len(
                items
            ),
            "approved": len(
                approved
            ),
            "rejected": (
                len(
                    prepared_with_rejected
                )
                - len(
                    approved
                )
            ),
            "returned": len(
                returned
            ),
            "include_rejected": bool(
                include_rejected
            ),
            "reports_recorded": len(
                reports
            ),
            "live_enabled": (
                self.engine.enabled
            ),
        }

        return returned

    orchestrate = prepare

    def prepare_one(
        self,
        opportunity: Any,
        *,
        include_rejected: bool = False,
    ) -> Any | None:
        prepared = self.prepare(
            [
                opportunity
            ],
            include_rejected=(
                include_rejected
            ),
        )

        return (
            prepared[0]
            if prepared
            else None
        )

    def execute(
        self,
        execution_plan: Any,
        *,
        include_rejected: bool = False,
    ) -> Any:
        """
        Interface legada segura.

        Quando recebe ExecutionPlan, cria apenas
        o relatório READY ou REJECTED.

        O plano não é enviado ao executor e não
        é tratado como uma ordem.

        Quando recebe oportunidades, executa
        prepare().
        """

        if isinstance(
            execution_plan,
            ExecutionPlan,
        ):
            report = self.reporter.create(
                execution_plan
            )

            self.statistics.update(
                report
            )

            self.last_report = {
                "mode": "PLAN",
                "input": 1,
                "approved": int(
                    execution_plan.approved
                ),
                "rejected": int(
                    not execution_plan.approved
                ),
                "returned": 1,
                "reports_recorded": 1,
                "live_enabled": (
                    self.engine.enabled
                ),
            }

            return report

        return self.prepare(
            execution_plan,
            include_rejected=(
                include_rejected
            ),
        )

    def execute_order(
        self,
        order: Any,
        venue: Any = None,
        *,
        enabled: bool | None = None,
        executor: Any = None,
    ) -> dict[str, Any]:
        """
        Encaminha uma ordem já criada pelo OMS
        ao ExecutionEngine.

        Esta operação continua protegida por:

        - enabled;
        - executor explicitamente configurado.
        """

        report = self.engine.execute(
            order,
            venue,
            enabled=enabled,
            executor=executor,
        )

        self.statistics.update(
            report
        )

        self.last_report = {
            "mode": "LIVE",
            "input": 1,
            "approved": int(
                bool(
                    report.get(
                        "executed"
                    )
                )
            ),
            "rejected": int(
                not bool(
                    report.get(
                        "executed"
                    )
                )
            ),
            "returned": 1,
            "reports_recorded": 1,
            "status": report.get(
                "status"
            ),
            "live_enabled": (
                self.engine.enabled
                if enabled is None
                else bool(
                    enabled
                )
            ),
        }

        return report

    live_execute = execute_order

    def clear_statistics(
        self,
    ) -> None:
        self.statistics.clear()

    def status(
        self,
    ) -> dict[str, Any]:
        return {
            "engine": (
                self.engine.status()
            ),
            "statistics": (
                self.statistics.summary()
            ),
            "last_report": dict(
                self.last_report
            ),
        }


execution_orchestrator = (
    ExecutionOrchestrator()
)