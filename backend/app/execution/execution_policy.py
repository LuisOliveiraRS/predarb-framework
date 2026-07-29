from __future__ import annotations

from math import isfinite
from typing import Any


class ExecutionPolicy:
    """
    Política segura e determinística para
    planos de execução de arbitragem.

    A política apenas define parâmetros.
    Ela não envia ordens.
    """

    DEFAULT_SIMULTANEOUS = True
    DEFAULT_MAX_LATENCY = 0.5
    DEFAULT_RETRY = 2

    DEFAULT_CANCEL_ON_FAILURE = True

    @staticmethod
    def _non_negative_number(
        value: Any,
        field_name: str,
    ) -> float:
        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if (
            not isfinite(number)
            or number < 0
        ):
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser finito e não negativo."
            )

        return number

    @staticmethod
    def _retry(
        value: Any,
    ) -> int:
        if isinstance(value, bool):
            raise TypeError(
                "retry não pode ser booleano."
            )

        try:
            retry = int(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                "retry deve ser inteiro."
            ) from exc

        if retry < 0:
            raise ValueError(
                "retry não pode ser negativo."
            )

        return retry

    def create(
        self,
        opportunity: Any = None,
        *,
        simultaneous: bool | None = None,
        max_latency: float | None = None,
        retry: int | None = None,
        cancel_on_failure: bool | None = None,
    ) -> dict[str, Any]:
        """
        Cria uma política de execução.

        opportunity é aceito para compatibilidade
        e para futuras políticas adaptativas.
        """

        del opportunity

        resolved_simultaneous = (
            self.DEFAULT_SIMULTANEOUS
            if simultaneous is None
            else bool(simultaneous)
        )

        resolved_max_latency = (
            self.DEFAULT_MAX_LATENCY
            if max_latency is None
            else max_latency
        )

        resolved_retry = (
            self.DEFAULT_RETRY
            if retry is None
            else retry
        )

        resolved_cancel = (
            self.DEFAULT_CANCEL_ON_FAILURE
            if cancel_on_failure is None
            else bool(cancel_on_failure)
        )

        return {
            "simultaneous": (
                resolved_simultaneous
            ),
            "max_latency": (
                self._non_negative_number(
                    resolved_max_latency,
                    "max_latency",
                )
            ),
            "retry": self._retry(
                resolved_retry
            ),
            "cancel_on_failure": (
                resolved_cancel
            ),
        }

    build = create


execution_policy = ExecutionPolicy()