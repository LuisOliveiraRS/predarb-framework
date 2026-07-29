from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from threading import RLock
from typing import Any

from app.pipeline.pipeline_result import (
    PipelineResult,
)


class PipelineMetrics:
    """
    Métricas consolidadas das execuções
    do Pipeline.

    Este componente fornece observabilidade.
    Ele não altera resultados e não controla
    os estágios.
    """

    def __init__(self) -> None:
        self._lock = RLock()

        self.reset()

    @staticmethod
    def _count_items(
        value: Any,
    ) -> int:
        """
        Conta itens sem falhar com objetos
        únicos, dicionários ou valores None.
        """

        if value is None:
            return 0

        if isinstance(
            value,
            Mapping,
        ):
            return 1

        if isinstance(
            value,
            (str, bytes),
        ):
            return 1

        try:
            return len(value)

        except TypeError:
            return 1

    def record(
        self,
        result: PipelineResult,
        *,
        pipeline_name: str = "default",
    ) -> None:
        """
        Registra uma execução concluída.
        """

        if not isinstance(
            result,
            PipelineResult,
        ):
            raise TypeError(
                "PipelineMetrics.record exige "
                "um PipelineResult."
            )

        context = result.context

        duration_ms = float(
            result.duration_ms or 0.0
        )

        market_count = self._count_items(
            context.markets,
        )

        match_count = self._count_items(
            context.get(
                "matches",
            )
        )

        opportunity_count = (
            self._count_items(
                context.opportunities,
            )
        )

        input_count = self._count_items(
            context.input_data,
        )

        output_count = self._count_items(
            result.output,
        )

        stage_count = len(
            result.stages,
        )

        stage_failures = sum(
            1
            for stage in result.stages
            if stage.get("status") == "error"
        )

        with self._lock:
            self.total_runs += 1

            if result.success:
                self.successful_runs += 1

            else:
                self.failed_runs += 1

            if result.halted:
                self.halted_runs += 1

            self.total_input_items += (
                input_count
            )

            self.total_output_items += (
                output_count
            )

            self.total_markets += (
                market_count
            )

            self.total_matches += (
                match_count
            )

            self.total_opportunities += (
                opportunity_count
            )

            self.total_stages += (
                stage_count
            )

            self.stage_failures += (
                stage_failures
            )

            self.total_execution_time_ms += (
                duration_ms
            )

            self.last_execution_time_ms = (
                duration_ms
            )

            # Campo legado preservado.
            # A unidade oficial é milissegundos.
            self.execution_time = duration_ms

            self.last_pipeline = pipeline_name
            self.last_success = result.success
            self.last_halted = result.halted

            self.last_error = (
                result.errors[-1]["message"]
                if result.errors
                else None
            )

            self.last_started_at = (
                context.started_at
            )

            self.last_finished_at = (
                context.finished_at
            )

    def record_exception(
        self,
        error: BaseException,
        *,
        pipeline_name: str = "default",
        duration_ms: float = 0.0,
    ) -> None:
        """
        Registra uma exceção que escapou
        da execução do Pipeline.
        """

        normalized_duration = max(
            0.0,
            float(duration_ms),
        )

        with self._lock:
            self.total_runs += 1
            self.failed_runs += 1
            self.halted_runs += 1

            self.total_execution_time_ms += (
                normalized_duration
            )

            self.last_execution_time_ms = (
                normalized_duration
            )

            self.execution_time = (
                normalized_duration
            )

            self.last_pipeline = pipeline_name
            self.last_success = False
            self.last_halted = True
            self.last_error = str(error)

            self.last_finished_at = datetime.now(
                timezone.utc,
            )

    @property
    def average_execution_time_ms(
        self,
    ) -> float:
        """
        Retorna a duração média das execuções.
        """

        with self._lock:
            if self.total_runs == 0:
                return 0.0

            return round(
                self.total_execution_time_ms
                / self.total_runs,
                3,
            )

    @staticmethod
    def _serialize_datetime(
        value: datetime | None,
    ) -> str | None:
        if value is None:
            return None

        return value.isoformat()

    def snapshot(
        self,
    ) -> dict[str, Any]:
        """
        Retorna uma cópia serializável
        das métricas atuais.
        """

        with self._lock:
            success_rate = (
                self.successful_runs
                / self.total_runs
                * 100
                if self.total_runs
                else 0.0
            )

            return {
                "total_runs": (
                    self.total_runs
                ),
                "successful_runs": (
                    self.successful_runs
                ),
                "failed_runs": (
                    self.failed_runs
                ),
                "halted_runs": (
                    self.halted_runs
                ),
                "success_rate": round(
                    success_rate,
                    2,
                ),
                "total_input_items": (
                    self.total_input_items
                ),
                "total_output_items": (
                    self.total_output_items
                ),
                "total_markets": (
                    self.total_markets
                ),
                "total_matches": (
                    self.total_matches
                ),
                "total_opportunities": (
                    self.total_opportunities
                ),
                "total_stages": (
                    self.total_stages
                ),
                "stage_failures": (
                    self.stage_failures
                ),
                "total_execution_time_ms": round(
                    self.total_execution_time_ms,
                    3,
                ),
                "last_execution_time_ms": round(
                    self.last_execution_time_ms,
                    3,
                ),
                "average_execution_time_ms": (
                    self.average_execution_time_ms
                ),
                "last_pipeline": (
                    self.last_pipeline
                ),
                "last_success": (
                    self.last_success
                ),
                "last_halted": (
                    self.last_halted
                ),
                "last_error": (
                    self.last_error
                ),
                "last_started_at": (
                    self._serialize_datetime(
                        self.last_started_at
                    )
                ),
                "last_finished_at": (
                    self._serialize_datetime(
                        self.last_finished_at
                    )
                ),
            }

    def reset(self) -> None:
        """
        Reinicia todas as métricas.
        """

        with self._lock:
            self.total_runs = 0
            self.successful_runs = 0
            self.failed_runs = 0
            self.halted_runs = 0

            self.total_input_items = 0
            self.total_output_items = 0

            # Campos da implementação antiga.
            self.total_markets = 0
            self.total_matches = 0
            self.total_opportunities = 0

            self.total_stages = 0
            self.stage_failures = 0

            self.total_execution_time_ms = 0.0
            self.last_execution_time_ms = 0.0

            # Campo legado preservado.
            self.execution_time = 0.0

            self.last_pipeline: str | None = None
            self.last_success: bool | None = None
            self.last_halted: bool | None = None
            self.last_error: str | None = None

            self.last_started_at: (
                datetime | None
            ) = None

            self.last_finished_at: (
                datetime | None
            ) = None


pipeline_metrics = PipelineMetrics()