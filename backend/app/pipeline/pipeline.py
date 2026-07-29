from __future__ import annotations

import inspect
from collections.abc import Iterable
from time import perf_counter
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.pipeline_result import (
    PipelineResult,
)
from app.pipeline.pipeline_stage import (
    PipelineStage,
)


class Pipeline:
    """
    Orquestrador oficial dos estágios
    do PredArb.

    Contrato canônico:

        entrada
            ↓
        PipelineContext
            ↓
        estágios
            ↓
        PipelineResult

    O método run() permanece como fachada
    de compatibilidade e retorna somente
    o valor final.
    """

    def __init__(
        self,
        stages: Iterable[Any] | None = None,
        *,
        name: str = "default",
        stop_on_error: bool = True,
    ) -> None:
        self.name = (
            str(name).strip()
            or "default"
        )

        self.stop_on_error = bool(
            stop_on_error,
        )

        self.stages: list[Any] = []

        if stages is not None:
            for stage in stages:
                self.add_stage(
                    stage,
                )

    @staticmethod
    def _stage_name(
        stage: Any,
    ) -> str:
        """
        Recupera o nome do estágio.
        """

        configured_name = getattr(
            stage,
            "name",
            None,
        )

        if (
            isinstance(
                configured_name,
                str,
            )
            and configured_name.strip()
        ):
            return configured_name.strip()

        return stage.__class__.__name__

    @staticmethod
    def _stage_callable(
        stage: Any,
    ):
        """
        Seleciona process() ou execute()
        sem exigir herança.
        """

        if isinstance(
            stage,
            PipelineStage,
        ):
            return stage.process

        process = getattr(
            stage,
            "process",
            None,
        )

        if callable(
            process,
        ):
            return process

        execute = getattr(
            stage,
            "execute",
            None,
        )

        if callable(
            execute,
        ):
            return execute

        raise TypeError(
            f"O estágio "
            f"{stage.__class__.__name__!r} "
            "não implementa process(context) "
            "nem execute(context)."
        )

    def add_stage(
        self,
        stage: Any,
    ) -> Pipeline:
        """
        Adiciona um estágio validado.
        """

        if stage is None:
            raise ValueError(
                "Não é possível adicionar "
                "um estágio None."
            )

        self._stage_callable(
            stage,
        )

        self.stages.append(
            stage,
        )

        return self

    def remove_stage(
        self,
        stage_or_name: Any,
    ) -> bool:
        """
        Remove um estágio pela instância
        ou pelo nome.
        """

        for index, stage in enumerate(
            self.stages,
        ):
            if (
                stage is stage_or_name
                or self._stage_name(stage)
                == stage_or_name
            ):
                self.stages.pop(
                    index,
                )

                return True

        return False

    def clear(self) -> None:
        """
        Remove todos os estágios.
        """

        self.stages.clear()

    def execute(
        self,
        data: Any = None,
        *,
        raise_on_error: bool | None = None,
    ) -> PipelineResult:
        """
        Executa todos os estágios e retorna
        um PipelineResult.
        """

        context = PipelineContext.ensure(
            data,
        )

        should_raise = bool(
            raise_on_error,
        )

        for stage in self.stages:
            if context.halted:
                break

            stage_name = self._stage_name(
                stage,
            )

            stage_callable = (
                self._stage_callable(
                    stage,
                )
            )

            context.current_stage = stage_name

            started_at = perf_counter()

            try:
                stage_result = stage_callable(
                    context,
                )

                if inspect.isawaitable(
                    stage_result,
                ):
                    raise TypeError(
                        f"O estágio {stage_name!r} "
                        "retornou uma coroutine. "
                        "O Pipeline atual é síncrono."
                    )

                if stage_result is None:
                    context.halt(
                        f"O estágio {stage_name!r} "
                        "retornou None."
                    )

                    status = "halted"
                    detail = context.halt_reason

                elif isinstance(
                    stage_result,
                    PipelineResult,
                ):
                    context = (
                        stage_result.context
                    )

                    status = (
                        "success"
                        if stage_result.success
                        else "error"
                    )

                    detail = (
                        context.halt_reason
                    )

                    if (
                        not stage_result.success
                        and self.stop_on_error
                    ):
                        context.halt(
                            f"O estágio "
                            f"{stage_name!r} "
                            "retornou um resultado "
                            "com erro."
                        )

                        detail = (
                            context.halt_reason
                        )

                elif isinstance(
                    stage_result,
                    PipelineContext,
                ):
                    context = stage_result

                    status = (
                        "halted"
                        if context.halted
                        else "success"
                    )

                    detail = (
                        context.halt_reason
                    )

                else:
                    context.set_output(
                        stage_result,
                    )

                    status = "success"
                    detail = None

                duration_ms = (
                    perf_counter()
                    - started_at
                ) * 1000

                context.add_stage_record(
                    stage=stage_name,
                    status=status,
                    duration_ms=duration_ms,
                    detail=detail,
                )

            except Exception as exc:
                duration_ms = (
                    perf_counter()
                    - started_at
                ) * 1000

                context.add_error(
                    stage_name,
                    exc,
                )

                context.add_stage_record(
                    stage=stage_name,
                    status="error",
                    duration_ms=duration_ms,
                    detail=str(exc),
                )

                if should_raise:
                    context.complete()
                    raise

                if self.stop_on_error:
                    context.halt(
                        "Execução interrompida "
                        f"no estágio {stage_name!r}."
                    )

        context.complete()

        return PipelineResult(
            context,
        )

    def run(
        self,
        data: Any = None,
        *,
        return_result: bool = False,
        raise_on_error: bool | None = None,
    ) -> Any:
        """
        Executa o Pipeline.

        Por compatibilidade com o ArbitrageEngine,
        retorna somente result.output.

        Para receber o PipelineResult completo:

            pipeline.run(
                data,
                return_result=True,
            )
        """

        result = self.execute(
            data,
            raise_on_error=raise_on_error,
        )

        if return_result:
            return result

        return result.output

    process = execute

    def __call__(
        self,
        data: Any = None,
    ) -> PipelineResult:
        return self.execute(
            data,
        )