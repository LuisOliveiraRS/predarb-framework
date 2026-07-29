from __future__ import annotations

import logging

from app.kernel.kernel import Kernel
from app.kernel.kernel_builder import kernel_builder


logger = logging.getLogger(__name__)


class KernelBootstrap:
    """
    Ponto oficial de entrada para o ciclo
    de vida do Kernel.

    O application.py deve utilizar somente:

        kernel_bootstrap.start()
        kernel_bootstrap.stop()
    """

    def __init__(self) -> None:
        self._kernel: Kernel | None = None

    @property
    def started(self) -> bool:
        """
        Indica se o Kernel está ativo.
        """

        return (
            self._kernel is not None
            and self._kernel.running
        )

    def start(self) -> Kernel:
        """
        Inicializa o Kernel de forma idempotente.
        """

        if self.started:
            logger.debug(
                "Bootstrap ignorado: Kernel já iniciado."
            )

            return self._kernel

        logger.info(
            "Iniciando bootstrap do Kernel."
        )

        self._kernel = kernel_builder.build()

        return self._kernel

    def stop(self) -> None:
        """
        Encerra o Kernel de forma segura.
        """

        if self._kernel is None:
            logger.debug(
                "Bootstrap ainda não foi iniciado."
            )
            return

        logger.info(
            "Encerrando Kernel pelo bootstrap."
        )

        kernel_builder.shutdown()

        self._kernel = None

    def get_kernel(self) -> Kernel:
        """
        Retorna o Kernel oficial.

        Inicializa o Kernel caso o bootstrap
        ainda não tenha sido executado.
        """

        if self._kernel is None:
            return self.start()

        return self._kernel


kernel_bootstrap = KernelBootstrap()