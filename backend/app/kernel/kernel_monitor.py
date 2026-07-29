from __future__ import annotations

from datetime import datetime, timezone
from time import monotonic
from typing import Any

from app.kernel.kernel_context import kernel_context
from app.kernel.kernel_services import kernel_services


class KernelMonitor:
    """
    Monitor interno do Kernel.

    Responsabilidades:

    - fornecer heartbeat;
    - informar o estado atual do Kernel;
    - medir o tempo de atividade;
    - contabilizar serviços registrados;
    - contabilizar dependências disponíveis;
    - fornecer dados para health checks.
    """

    def __init__(self) -> None:
        self._started_at = monotonic()

    @staticmethod
    def _get_kernel_state() -> str:
        """
        Recupera o estado atual do Kernel.

        O import é realizado dentro do método para
        evitar dependência circular durante o bootstrap.
        """

        try:
            from app.kernel.kernel import kernel

            state = getattr(
                kernel,
                "state",
                None,
            )

            if state is None:
                return "UNKNOWN"

            state_value = getattr(
                state,
                "value",
                None,
            )

            if state_value is not None:
                return str(state_value)

            return str(state)

        except Exception:
            return "UNKNOWN"

    @staticmethod
    def _resolve_health(
        kernel_state: str,
    ) -> str:
        """
        Converte o estado do Kernel em uma
        classificação de saúde.
        """

        normalized_state = kernel_state.upper()

        if normalized_state == "RUNNING":
            return "healthy"

        if normalized_state in {
            "CREATED",
            "INITIALIZING",
            "PAUSED",
        }:
            return "degraded"

        if normalized_state == "STOPPED":
            return "stopped"

        if normalized_state == "ERROR":
            return "unhealthy"

        return "unknown"

    def uptime_seconds(self) -> float:
        """
        Retorna o tempo de atividade do monitor.
        """

        return round(
            monotonic() - self._started_at,
            3,
        )

    def heartbeat(self) -> dict[str, Any]:
        """
        Retorna um diagnóstico consolidado
        do Kernel.
        """

        kernel_state = self._get_kernel_state()

        context_snapshot = (
            kernel_context.snapshot()
        )

        services_snapshot = (
            kernel_services.snapshot()
        )

        context_ready = sum(
            1
            for value in context_snapshot.values()
            if value is not None
        )

        return {
            "status": self._resolve_health(
                kernel_state,
            ),
            "kernel_state": kernel_state,
            "timestamp": datetime.now(
                timezone.utc,
            ).isoformat(),
            "uptime_seconds": (
                self.uptime_seconds()
            ),
            "services": {
                "registered": len(
                    services_snapshot,
                ),
                "names": list(
                    services_snapshot.keys(),
                ),
            },
            "context": {
                "entries": len(
                    context_snapshot,
                ),
                "ready": context_ready,
                "pending": (
                    len(context_snapshot)
                    - context_ready
                ),
            },
        }

    def status(self) -> dict[str, Any]:
        """
        Alias de heartbeat para utilização
        em endpoints e diagnósticos.
        """

        return self.heartbeat()

    def is_alive(self) -> bool:
        """
        Indica se o Kernel está em execução.
        """

        return (
            self._get_kernel_state().upper()
            == "RUNNING"
        )

    def reset_uptime(self) -> None:
        """
        Reinicia a contagem de tempo do monitor.
        """

        self._started_at = monotonic()


kernel_monitor = KernelMonitor()