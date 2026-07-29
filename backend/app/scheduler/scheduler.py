from __future__ import annotations

import logging
from threading import RLock
from typing import Any, Callable

from apscheduler.schedulers.background import (
    BackgroundScheduler,
)
from apscheduler.schedulers.base import (
    STATE_STOPPED,
)


logger = logging.getLogger(__name__)


class SchedulerService:
    """
    Serviço oficial de agendamento do PredArb.

    Responsabilidades:

    - registrar jobs;
    - evitar jobs duplicados;
    - iniciar o scheduler;
    - encerrar o scheduler;
    - permitir reinicialização em testes
      e novos ciclos da aplicação.
    """

    def __init__(self) -> None:
        self._lock = RLock()
        self._started_once = False

        self.scheduler = self._create_scheduler()

    @staticmethod
    def _create_scheduler() -> BackgroundScheduler:
        """
        Cria a instância interna do APScheduler.
        """

        return BackgroundScheduler(
            job_defaults={
                "coalesce": True,
                "max_instances": 1,
                "misfire_grace_time": 30,
            }
        )

    @property
    def running(self) -> bool:
        """
        Indica se o scheduler está ativo.
        """

        return bool(
            self.scheduler.running
        )

    def _prepare_for_new_cycle(self) -> None:
        """
        Recria o scheduler após um shutdown.

        Uma instância encerrada do APScheduler não
        deve ser reutilizada em um novo ciclo.
        """

        if (
            self._started_once
            and self.scheduler.state == STATE_STOPPED
        ):
            self.scheduler = (
                self._create_scheduler()
            )

    def add_job(
        self,
        func: Callable[..., Any],
        seconds: int,
        *,
        job_id: str | None = None,
        replace_existing: bool = True,
        **kwargs: Any,
    ) -> Any:
        """
        Adiciona um job periódico.

        Quando nenhum ID for informado, utiliza o
        nome da função para evitar duplicidade.
        """

        if not callable(func):
            raise TypeError(
                "O job deve receber uma função executável."
            )

        if not isinstance(seconds, int):
            raise TypeError(
                "O intervalo do job deve ser um inteiro."
            )

        if seconds <= 0:
            raise ValueError(
                "O intervalo do job deve ser maior que zero."
            )

        resolved_job_id = (
            job_id
            or getattr(
                func,
                "__name__",
                func.__class__.__name__,
            )
        )

        with self._lock:
            self._prepare_for_new_cycle()

            return self.scheduler.add_job(
                func,
                trigger="interval",
                seconds=seconds,
                id=resolved_job_id,
                replace_existing=replace_existing,
                **kwargs,
            )

    def start(self) -> bool:
        """
        Inicia o scheduler de forma idempotente.
        """

        with self._lock:
            if self.running:
                logger.debug(
                    "Scheduler já está em execução."
                )
                return False

            self._prepare_for_new_cycle()

            self.scheduler.start()
            self._started_once = True

        logger.info(
            "Scheduler iniciado."
        )

        return True

    def shutdown(
        self,
        *,
        wait: bool = False,
    ) -> bool:
        """
        Encerra o scheduler de forma idempotente.
        """

        with self._lock:
            if not self.running:
                logger.debug(
                    "Scheduler já está encerrado."
                )
                return False

            self.scheduler.shutdown(
                wait=wait,
            )

        logger.info(
            "Scheduler encerrado."
        )

        return True

    def stop(
        self,
        *,
        wait: bool = False,
    ) -> bool:
        """
        Alias compatível para shutdown().
        """

        return self.shutdown(
            wait=wait,
        )

    def get_jobs(self) -> list[Any]:
        """
        Retorna os jobs registrados.
        """

        return list(
            self.scheduler.get_jobs(),
        )

    def remove_job(
        self,
        job_id: str,
    ) -> bool:
        """
        Remove um job pelo ID.
        """

        job = self.scheduler.get_job(
            job_id,
        )

        if job is None:
            return False

        self.scheduler.remove_job(
            job_id,
        )

        return True

    def status(self) -> dict[str, Any]:
        """
        Retorna o estado operacional.
        """

        jobs = self.get_jobs()

        return {
            "running": self.running,
            "jobs": len(jobs),
            "job_ids": [
                job.id
                for job in jobs
            ],
        }


scheduler_service = SchedulerService()