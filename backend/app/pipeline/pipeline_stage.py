from __future__ import annotations

from abc import ABC
from typing import Any


class PipelineStage(ABC):
    """
    Contrato oficial de um estágio do Pipeline.

    O método canônico é process(context).

    Durante a consolidação, o contrato também aceita
    estágios legados que implementam apenas
    execute(context).
    """

    @property
    def name(self) -> str:
        """
        Retorna um nome estável para diagnóstico
        e métricas.
        """

        return self.__class__.__name__

    def process(
        self,
        context: Any,
    ) -> Any:
        """
        Processa o contexto.

        Novos estágios devem sobrescrever este método.

        Caso o estágio implemente apenas execute(),
        a chamada será delegada para preservar
        compatibilidade com o código existente.
        """

        execute_implementation = (
            type(self).__dict__.get(
                "execute",
            )
        )

        if (
            execute_implementation is not None
            and execute_implementation
            is not PipelineStage.execute
        ):
            return execute_implementation(
                self,
                context,
            )

        raise NotImplementedError(
            f"O estágio {self.name!r} deve "
            "implementar process() ou execute()."
        )

    def execute(
        self,
        context: Any,
    ) -> Any:
        """
        Alias de compatibilidade para estágios
        que ainda utilizam execute().
        """

        process_implementation = (
            type(self).__dict__.get(
                "process",
            )
        )

        if (
            process_implementation is not None
            and process_implementation
            is not PipelineStage.process
        ):
            return process_implementation(
                self,
                context,
            )

        raise NotImplementedError(
            f"O estágio {self.name!r} deve "
            "implementar process() ou execute()."
        )

    def __call__(
        self,
        context: Any,
    ) -> Any:
        return self.process(
            context,
        )