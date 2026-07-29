from __future__ import annotations

from collections.abc import (
    Iterable,
    Iterator,
    Mapping,
)
from datetime import datetime
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)


class PipelineResult:
    """
    Resultado oficial de uma execução
    do Pipeline.

    Mantém o contexto completo para auditoria
    e disponibiliza o valor final por meio
    da propriedade output.
    """

    def __init__(
        self,
        context: PipelineContext,
    ) -> None:
        if not isinstance(
            context,
            PipelineContext,
        ):
            raise TypeError(
                "PipelineResult exige uma "
                "instância de PipelineContext."
            )

        self.context = context

    @property
    def success(self) -> bool:
        """
        Indica se o Pipeline terminou
        sem exceções registradas.
        """

        return not self.context.errors

    @property
    def halted(self) -> bool:
        """
        Indica se o Pipeline foi interrompido.
        """

        return self.context.halted

    @property
    def output(self) -> Any:
        """
        Retorna o resultado final.
        """

        return self.context.output

    @property
    def data(self) -> Any:
        """
        Alias de output.
        """

        return self.output

    @property
    def opportunities(self) -> list[Any]:
        """
        Preserva a propriedade legada
        de oportunidades.
        """

        return list(
            self.context.opportunities
            or []
        )

    @property
    def positions(self) -> list[Any]:
        """
        Preserva a propriedade legada
        de posições.
        """

        return list(
            self.context.positions
            or []
        )

    @property
    def errors(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.context.errors,
        )

    @property
    def stages(
        self,
    ) -> list[dict[str, Any]]:
        return list(
            self.context.stage_history,
        )

    @property
    def duration_ms(
        self,
    ) -> float | None:
        """
        Retorna a duração total do Pipeline.
        """

        started_at = self.context.started_at
        finished_at = self.context.finished_at

        if (
            not isinstance(
                started_at,
                datetime,
            )
            or not isinstance(
                finished_at,
                datetime,
            )
        ):
            return None

        return round(
            max(
                0.0,
                (
                    finished_at
                    - started_at
                ).total_seconds()
                * 1000,
            ),
            3,
        )

    def unwrap(self) -> Any:
        """
        Retorna somente o valor final.
        """

        return self.output

    def to_dict(self) -> dict[str, Any]:
        """
        Retorna uma representação estruturada.
        """

        return {
            "success": self.success,
            "halted": self.halted,
            "halt_reason": (
                self.context.halt_reason
            ),
            "duration_ms": self.duration_ms,
            "output": self.output,
            "errors": self.errors,
            "stages": self.stages,
        }

    def __bool__(self) -> bool:
        if not self.success:
            return False

        return bool(
            self.output,
        )

    def __len__(self) -> int:
        value = self.output

        if value is None:
            return 0

        try:
            return len(
                value,
            )

        except TypeError:
            return 1

    def __iter__(
        self,
    ) -> Iterator[Any]:
        value = self.output

        if value is None:
            return iter(())

        if isinstance(
            value,
            Mapping,
        ):
            return iter(
                (
                    value,
                )
            )

        if (
            isinstance(
                value,
                Iterable,
            )
            and not isinstance(
                value,
                (str, bytes),
            )
        ):
            return iter(
                value,
            )

        return iter(
            (
                value,
            )
        )