from __future__ import annotations

from threading import RLock
from time import perf_counter
from typing import Any

from app.pipeline.pipeline import Pipeline
from app.pipeline.pipeline_builder import (
    PipelineBuilder,
    pipeline_builder,
)
from app.pipeline.pipeline_metrics import (
    PipelineMetrics,
    pipeline_metrics,
)
from app.pipeline.pipeline_result import PipelineResult


class PipelineManager:
    """
    Registro e executor oficial dos Pipelines.

    Pipelines registrados na inicialização:

        analysis
        paper
        live

    O Pipeline padrão é o analysis.
    """

    ANALYSIS_PIPELINE = PipelineBuilder.ANALYSIS_NAME
    PAPER_PIPELINE = PipelineBuilder.PAPER_NAME
    LIVE_PIPELINE = PipelineBuilder.LIVE_NAME

    DEFAULT_PIPELINE = ANALYSIS_PIPELINE

    def __init__(
        self,
        *,
        builder: PipelineBuilder | None = None,
        metrics: PipelineMetrics | None = None,
    ) -> None:
        self._builder = builder or pipeline_builder
        self._metrics = metrics or pipeline_metrics

        self._pipelines: dict[str, Pipeline] = {}
        self._lock = RLock()

        self.reset_standard_pipelines()

    @staticmethod
    def _normalize_name(
        name: str,
    ) -> str:
        """
        Valida e normaliza o nome de um Pipeline.
        """

        if not isinstance(name, str):
            raise TypeError(
                "O nome do Pipeline deve ser uma string."
            )

        normalized = name.strip().lower()

        if not normalized:
            raise ValueError(
                "O nome do Pipeline não pode ser vazio."
            )

        return normalized

    @property
    def pipeline(self) -> Pipeline:
        """
        Pipeline padrão.

        Preserva compatibilidade com o atributo
        pipeline da implementação anterior.
        """

        return self.require(
            self.DEFAULT_PIPELINE,
        )

    @pipeline.setter
    def pipeline(
        self,
        value: Pipeline,
    ) -> None:
        self.register(
            self.DEFAULT_PIPELINE,
            value,
            replace=True,
        )

    def reset_standard_pipelines(self) -> None:
        """
        Reconstrói os três Pipelines oficiais.

        O Pipeline live é criado desabilitado.
        """

        analysis = self._builder.build_analysis()

        paper = self._builder.build_paper()

        live = self._builder.build_live(
            enabled=False,
        )

        with self._lock:
            self._pipelines.clear()

            self._pipelines[
                self.ANALYSIS_PIPELINE
            ] = analysis

            self._pipelines[
                self.PAPER_PIPELINE
            ] = paper

            self._pipelines[
                self.LIVE_PIPELINE
            ] = live

    def register(
        self,
        name: str,
        pipeline: Pipeline,
        *,
        replace: bool = True,
    ) -> Pipeline:
        """
        Registra um Pipeline.
        """

        normalized_name = self._normalize_name(
            name
        )

        if not isinstance(
            pipeline,
            Pipeline,
        ):
            raise TypeError(
                "O registro exige uma instância "
                "de Pipeline."
            )

        with self._lock:
            if (
                normalized_name in self._pipelines
                and not replace
            ):
                raise KeyError(
                    "Já existe um Pipeline registrado: "
                    f"{normalized_name}"
                )

            self._pipelines[
                normalized_name
            ] = pipeline

        return pipeline

    def get(
        self,
        name: str = DEFAULT_PIPELINE,
        default: Any = None,
    ) -> Pipeline | Any:
        """
        Recupera um Pipeline.
        """

        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            return self._pipelines.get(
                normalized_name,
                default,
            )

    def require(
        self,
        name: str = DEFAULT_PIPELINE,
    ) -> Pipeline:
        """
        Recupera um Pipeline obrigatório.
        """

        normalized_name = self._normalize_name(
            name
        )

        pipeline = self.get(
            normalized_name
        )

        if pipeline is None:
            raise LookupError(
                "Pipeline não registrado: "
                f"{normalized_name}"
            )

        return pipeline

    def exists(
        self,
        name: str,
    ) -> bool:
        normalized_name = self._normalize_name(
            name
        )

        with self._lock:
            return (
                normalized_name
                in self._pipelines
            )

    def names(self) -> list[str]:
        """
        Retorna os Pipelines registrados.
        """

        with self._lock:
            return list(
                self._pipelines.keys()
            )

    def all(self) -> dict[str, Pipeline]:
        """
        Retorna uma cópia do registro.
        """

        with self._lock:
            return dict(
                self._pipelines
            )

    def rebuild(
        self,
        name: str = DEFAULT_PIPELINE,
        *,
        stages: list[Any] | None = None,
        stop_on_error: bool = True,
        **options: Any,
    ) -> Pipeline:
        """
        Reconstrói um Pipeline.

        Para Pipelines personalizados, informe stages.
        """

        normalized_name = self._normalize_name(
            name
        )

        if stages is not None:
            pipeline = self._builder.build(
                stages,
                name=normalized_name,
                stop_on_error=stop_on_error,
            )

        elif normalized_name == self.ANALYSIS_PIPELINE:
            pipeline = self._builder.build_analysis(
                name=normalized_name,
                stop_on_error=stop_on_error,
                **options,
            )

        elif normalized_name == self.PAPER_PIPELINE:
            pipeline = self._builder.build_paper(
                name=normalized_name,
                stop_on_error=stop_on_error,
                **options,
            )

        elif normalized_name == self.LIVE_PIPELINE:
            pipeline = self._builder.build_live(
                name=normalized_name,
                stop_on_error=stop_on_error,
                **options,
            )

        else:
            raise ValueError(
                "Para reconstruir um Pipeline "
                "personalizado é necessário informar "
                "a lista stages."
            )

        return self.register(
            normalized_name,
            pipeline,
            replace=True,
        )

    def configure_live_execution(
        self,
        *,
        executor: Any,
        enabled: bool,
        venue_resolver: Any = None,
        fail_fast: bool = True,
        **options: Any,
    ) -> Pipeline:
        """
        Configura o Pipeline live.

        A execução permanece desabilitada quando
        enabled=False.
        """

        return self.rebuild(
            self.LIVE_PIPELINE,
            executor=executor,
            enabled=enabled,
            venue_resolver=venue_resolver,
            fail_fast=fail_fast,
            **options,
        )

    def execute(
        self,
        data: Any = None,
        *,
        pipeline_name: str = DEFAULT_PIPELINE,
        raise_on_error: bool | None = None,
    ) -> PipelineResult:
        """
        Executa um Pipeline e retorna o
        PipelineResult completo.
        """

        normalized_name = self._normalize_name(
            pipeline_name
        )

        pipeline = self.require(
            normalized_name
        )

        started_at = perf_counter()

        try:
            result = pipeline.execute(
                data,
                raise_on_error=raise_on_error,
            )

        except Exception as exc:
            duration_ms = (
                perf_counter()
                - started_at
            ) * 1000

            self._metrics.record_exception(
                exc,
                pipeline_name=normalized_name,
                duration_ms=duration_ms,
            )

            raise

        self._metrics.record(
            result,
            pipeline_name=normalized_name,
        )

        return result

    def run(
        self,
        data: Any = None,
        *,
        pipeline_name: str = DEFAULT_PIPELINE,
        return_result: bool = False,
        raise_on_error: bool | None = None,
    ) -> Any:
        """
        Executa um Pipeline.

        Por padrão retorna somente o output.
        """

        result = self.execute(
            data,
            pipeline_name=pipeline_name,
            raise_on_error=raise_on_error,
        )

        if return_result:
            return result

        return result.output

    def metrics(self) -> dict[str, Any]:
        return self._metrics.snapshot()

    def reset_metrics(self) -> None:
        self._metrics.reset()

    @staticmethod
    def _stage_names(
        pipeline: Pipeline,
    ) -> list[str]:
        return [
            getattr(
                stage,
                "name",
                stage.__class__.__name__,
            )
            for stage in pipeline.stages
        ]

    def status(self) -> dict[str, Any]:
        """
        Retorna a configuração atual.
        """

        pipelines = self.all()

        return {
            "default_pipeline": (
                self.DEFAULT_PIPELINE
            ),
            "pipelines": {
                name: {
                    "name": pipeline.name,
                    "stages": self._stage_names(
                        pipeline
                    ),
                    "stop_on_error": (
                        pipeline.stop_on_error
                    ),
                }
                for name, pipeline
                in pipelines.items()
            },
            "metrics": self.metrics(),
        }


pipeline_manager = PipelineManager()