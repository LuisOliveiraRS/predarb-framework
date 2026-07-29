from __future__ import annotations

import logging
from typing import Any

from app.kernel.kernel_context import kernel_context
from app.kernel.kernel_monitor import kernel_monitor
from app.kernel.kernel_services import kernel_services
from app.kernel.kernel_state import KernelState


logger = logging.getLogger(__name__)


class Kernel:
    """
    Núcleo principal do PredArb Framework.

    O Kernel controla:

    - estado global da aplicação;
    - registro de serviços;
    - contexto compartilhado;
    - monitoramento interno;
    - ciclo de inicialização e encerramento.

    O scheduler operacional da aplicação permanece
    sob responsabilidade do application.py.
    """

    def __init__(self) -> None:
        self.state: KernelState = KernelState.CREATED
        self.last_error: str | None = None

        self.context = kernel_context
        self.services = kernel_services
        self.monitor = kernel_monitor

    @property
    def initialized(self) -> bool:
        """
        Indica se o Kernel já foi inicializado.
        """

        return self.state in {
            KernelState.RUNNING,
            KernelState.PAUSED,
        }

    @property
    def running(self) -> bool:
        """
        Indica se o Kernel está em execução.
        """

        return self.state == KernelState.RUNNING

    def initialize(self) -> Kernel:
        """
        Inicializa o Kernel.

        A operação é idempotente: chamadas repetidas
        não reinicializam um Kernel já ativo.
        """

        if self.state == KernelState.RUNNING:
            logger.debug(
                "Kernel já está em execução."
            )
            return self

        if self.state == KernelState.INITIALIZING:
            logger.warning(
                "Kernel já está sendo inicializado."
            )
            return self

        logger.info(
            "Inicializando Kernel do PredArb."
        )

        self.state = KernelState.INITIALIZING
        self.last_error = None

        try:
            self.state = KernelState.RUNNING

            logger.info(
                "Kernel inicializado com sucesso."
            )

            return self

        except Exception as exc:
            self.state = KernelState.ERROR
            self.last_error = str(exc)

            logger.exception(
                "Falha durante a inicialização do Kernel."
            )

            raise

    def pause(self) -> None:
        """
        Coloca o Kernel em estado de pausa.
        """

        if self.state != KernelState.RUNNING:
            return

        self.state = KernelState.PAUSED

        logger.info(
            "Kernel pausado."
        )

    def resume(self) -> None:
        """
        Retoma a execução de um Kernel pausado.
        """

        if self.state != KernelState.PAUSED:
            return

        self.state = KernelState.RUNNING

        logger.info(
            "Kernel retomado."
        )

    def shutdown(self) -> None:
        """
        Encerra o Kernel de forma segura.

        A operação é idempotente e pode ser chamada
        mais de uma vez sem provocar erro.
        """

        if self.state == KernelState.STOPPED:
            logger.debug(
                "Kernel já está encerrado."
            )
            return

        logger.info(
            "Encerrando Kernel do PredArb."
        )

        try:
            self.state = KernelState.STOPPED

            logger.info(
                "Kernel encerrado com sucesso."
            )

        except Exception as exc:
            self.state = KernelState.ERROR
            self.last_error = str(exc)

            logger.exception(
                "Falha durante o encerramento do Kernel."
            )

            raise

    def heartbeat(self) -> Any:
        """
        Solicita um diagnóstico do Kernel.
        """

        return self.monitor.heartbeat()

    def status(self) -> dict[str, Any]:
        """
        Retorna o estado consolidado do Kernel.
        """

        return {
            "state": self.state.value,
            "initialized": self.initialized,
            "running": self.running,
            "services": len(
                self.services.services
            ),
            "last_error": self.last_error,
        }


kernel = Kernel()