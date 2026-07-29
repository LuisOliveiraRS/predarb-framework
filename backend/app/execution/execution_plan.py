from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any


def _number(
    value: Any,
    field_name: str,
    *,
    minimum: float | None = None,
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

    if not isfinite(number):
        raise ValueError(
            f"O campo {field_name!r} "
            "deve ser finito."
        )

    if (
        minimum is not None
        and number < minimum
    ):
        raise ValueError(
            f"O campo {field_name!r} deve ser "
            f"maior ou igual a {minimum}."
        )

    return number


@dataclass(slots=True)
class ExecutionPlan:
    """
    Plano validado para execução de uma
    arbitragem binária.

    O plano não envia ordens. Ele apenas descreve
    como a operação deverá ser executada pelo OMS.
    """

    question: str = ""

    yes_platform: str = ""
    no_platform: str = ""

    yes_price: float = 0.0
    no_price: float = 0.0

    yes_stake: float = 0.0
    no_stake: float = 0.0

    expected_profit: float = 0.0
    estimated_roi: float = 0.0

    max_latency: float = 0.5
    simultaneous: bool = True

    retry: int = 2
    cancel_on_failure: bool = True

    execute: bool = False
    reason: str = ""

    opportunity: Any = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    created_at: datetime = field(
        default_factory=lambda: datetime.now(
            timezone.utc
        )
    )

    def __post_init__(self) -> None:
        self.question = str(
            self.question or ""
        ).strip()

        self.yes_platform = str(
            self.yes_platform or ""
        ).strip()

        self.no_platform = str(
            self.no_platform or ""
        ).strip()

        self.reason = str(
            self.reason or ""
        ).strip()

        self.yes_price = _number(
            self.yes_price,
            "yes_price",
            minimum=0.0,
        )

        self.no_price = _number(
            self.no_price,
            "no_price",
            minimum=0.0,
        )

        self.yes_stake = _number(
            self.yes_stake,
            "yes_stake",
            minimum=0.0,
        )

        self.no_stake = _number(
            self.no_stake,
            "no_stake",
            minimum=0.0,
        )

        self.expected_profit = _number(
            self.expected_profit,
            "expected_profit",
        )

        self.estimated_roi = _number(
            self.estimated_roi,
            "estimated_roi",
        )

        self.max_latency = _number(
            self.max_latency,
            "max_latency",
            minimum=0.0,
        )

        if (
            self.yes_price > 1
            or self.no_price > 1
        ):
            raise ValueError(
                "yes_price e no_price devem "
                "estar entre 0 e 1."
            )

        if isinstance(self.retry, bool):
            raise TypeError(
                "retry não pode ser booleano."
            )

        try:
            self.retry = int(
                self.retry
            )

        except (TypeError, ValueError) as exc:
            raise TypeError(
                "retry deve ser inteiro."
            ) from exc

        if self.retry < 0:
            raise ValueError(
                "retry não pode ser negativo."
            )

        self.simultaneous = bool(
            self.simultaneous
        )

        self.cancel_on_failure = bool(
            self.cancel_on_failure
        )

        self.execute = bool(
            self.execute
        )

        self.metadata = dict(
            self.metadata or {}
        )

        if self.created_at.tzinfo is None:
            self.created_at = (
                self.created_at.replace(
                    tzinfo=timezone.utc
                )
            )

        if self.execute:
            missing: list[str] = []

            if not self.question:
                missing.append(
                    "question"
                )

            if not self.yes_platform:
                missing.append(
                    "yes_platform"
                )

            if not self.no_platform:
                missing.append(
                    "no_platform"
                )

            if self.yes_price <= 0:
                missing.append(
                    "yes_price"
                )

            if self.no_price <= 0:
                missing.append(
                    "no_price"
                )

            if self.yes_stake <= 0:
                missing.append(
                    "yes_stake"
                )

            if self.no_stake <= 0:
                missing.append(
                    "no_stake"
                )

            if self.expected_profit <= 0:
                missing.append(
                    "expected_profit"
                )

            if missing:
                raise ValueError(
                    "Plano aprovado sem campos "
                    "válidos: "
                    + ", ".join(missing)
                )

    @property
    def approved(self) -> bool:
        return self.execute

    @property
    def estimated_profit(self) -> float:
        """
        Alias para compatibilidade com a
        implementação anterior.
        """

        return self.expected_profit

    @estimated_profit.setter
    def estimated_profit(
        self,
        value: Any,
    ) -> None:
        self.expected_profit = _number(
            value,
            "estimated_profit",
        )

    @property
    def total_stake(self) -> float:
        return round(
            self.yes_stake
            + self.no_stake,
            2,
        )

    @property
    def total_price(self) -> float:
        return round(
            self.yes_price
            + self.no_price,
            6,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "yes_platform": (
                self.yes_platform
            ),
            "no_platform": (
                self.no_platform
            ),
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "yes_stake": self.yes_stake,
            "no_stake": self.no_stake,
            "total_stake": self.total_stake,
            "total_price": self.total_price,
            "expected_profit": (
                self.expected_profit
            ),
            "estimated_profit": (
                self.estimated_profit
            ),
            "estimated_roi": (
                self.estimated_roi
            ),
            "max_latency": (
                self.max_latency
            ),
            "simultaneous": (
                self.simultaneous
            ),
            "retry": self.retry,
            "cancel_on_failure": (
                self.cancel_on_failure
            ),
            "execute": self.execute,
            "approved": self.approved,
            "reason": self.reason,
            "metadata": dict(
                self.metadata
            ),
            "created_at": (
                self.created_at.isoformat()
            ),
        }