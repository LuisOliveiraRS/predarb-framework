from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Callable


logger = logging.getLogger(__name__)


class KernelScheduler:
    """
    Fachada do Kernel para o scheduler oficial.

    Este componente não cria um scheduler próprio.

    Todas as operações são delegadas para:

        app.scheduler.scheduler.scheduler_service

    O ciclo principal continua sendo controlado
    pelo application.py.
    """

    def __init__(self) -> None:
        self._lock = RLock()

    @staticmethod
    def _get_service() -> Any:
        """
        Recupera o scheduler oficial usando
        import tardio para evitar ciclos.
        """

        from app.scheduler.scheduler import (
            scheduler_service,
        )

        return scheduler_service

    @staticmethod
    def _read_running_state(
        target: Any,
    ) -> bool | None:
        """
        Tenta identificar o estado de execução
        de um objeto scheduler.
        """

        if target is None:
            return None

        running_attribute = getattr(
            target,
            "running",
            None,
        )

        if isinstance(
            running_attribute,
            bool,
        ):
            return running_attribute

        if callable(running_attribute):
            try:
                return bool(
                    running_attribute()
                )
            except TypeError:
                return None

        return None

    def running(self) -> bool:
        """
        Indica se o scheduler oficial
        está em execução.
        """

        service = self._get_service()

        service_state = self._read_running_state(
            service,
        )

        if service_state is not None:
            return service_state

        internal_scheduler = getattr(
            service,
            "scheduler",
            None,
        )

        scheduler_state = self._read_running_state(
            internal_scheduler,
        )

        if scheduler_state is not None:
            return scheduler_state

        return False

    def start(self) -> bool:
        """
        Inicia o scheduler oficial de forma
        idempotente.

        Retorna True quando realizou o início
        e False quando ele já estava ativo.
        """

        with self._lock:
            if self.running():
                logger.debug(
                    "Scheduler oficial já está ativo."
                )

                return False

            service = self._get_service()

            try:
                service.start()

            except Exception as exc:
                exception_name = (
                    exc.__class__.__name__
                )

                if exception_name in {
                    "SchedulerAlreadyRunningError",
                    "AlreadyRunningError",
                }:
                    logger.debug(
                        "Scheduler já estava ativo."
                    )

                    return False

                logger.exception(
                    "Erro ao iniciar o scheduler."
                )

                raise

            logger.info(
                "Scheduler oficial iniciado "
                "pela fachada do Kernel."
            )

            return True

    def shutdown(self) -> bool:
        """
        Encerra o scheduler oficial.

        Retorna True quando realizou o encerramento
        e False quando ele já estava parado.
        """

        with self._lock:
            if not self.running():
                logger.debug(
                    "Scheduler oficial já está parado."
                )

                return False

            service = self._get_service()

            try:
                service.shutdown()

            except Exception as exc:
                exception_name = (
                    exc.__class__.__name__
                )

                if exception_name in {
                    "SchedulerNotRunningError",
                    "NotRunningError",
                }:
                    logger.debug(
                        "Scheduler já estava parado."
                    )

                    return False

                logger.exception(
                    "Erro ao encerrar o scheduler."
                )

                raise

            logger.info(
                "Scheduler oficial encerrado "
                "pela fachada do Kernel."
            )

            return True

    def stop(self) -> bool:
        """
        Alias institucional para shutdown().
        """

        return self.shutdown()

    def add_job(
        self,
        function: Callable[..., Any],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """
        Registra um job no scheduler oficial.

        Mantém compatibilidade com chamadas como:

            kernel_scheduler.add_job(
                market_update_task,
                seconds=10,
            )
        """

        if not callable(function):
            raise TypeError(
                "O job deve receber uma "
                "função executável."
            )

        service = self._get_service()

        return service.add_job(
            function,
            *args,
            **kwargs,
        )

    def get_jobs(self) -> list[Any]:
        """
        Retorna os jobs registrados quando
        essa operação estiver disponível.
        """

        service = self._get_service()

        service_method = getattr(
            service,
            "get_jobs",
            None,
        )

        if callable(service_method):
            jobs = service_method()

            return list(
                jobs or [],
            )

        internal_scheduler = getattr(
            service,
            "scheduler",
            None,
        )

        scheduler_method = getattr(
            internal_scheduler,
            "get_jobs",
            None,
        )

        if callable(scheduler_method):
            jobs = scheduler_method()

            return list(
                jobs or [],
            )

        return []

    def status(self) -> dict[str, Any]:
        """
        Retorna o estado consolidado
        do scheduler oficial.
        """

        jobs = self.get_jobs()

        return {
            "running": self.running(),
            "jobs": len(jobs),
        }


kernel_scheduler = KernelScheduler()