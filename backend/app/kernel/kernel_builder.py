from __future__ import annotations

import logging

from app.kernel.kernel import Kernel, kernel


logger = logging.getLogger(__name__)


class KernelBuilder:
    """
    Responsável por construir e encerrar
    a instância oficial do Kernel.
    """

    def __init__(
        self,
        kernel_instance: Kernel | None = None,
    ) -> None:
        self._kernel = kernel_instance or kernel

    def build(self) -> Kernel:
        """
        Inicializa e retorna o Kernel oficial.
        """

        logger.debug(
            "Construindo Kernel."
        )

        self._kernel.initialize()

        return self._kernel

    def shutdown(self) -> None:
        """
        Encerra o Kernel oficial.
        """

        logger.debug(
            "Solicitando encerramento do Kernel."
        )

        self._kernel.shutdown()

    def get(self) -> Kernel:
        """
        Retorna a instância oficial sem
        executar uma nova inicialização.
        """

        return self._kernel


kernel_builder = KernelBuilder()