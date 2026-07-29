from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from app.execution.execution_plan import (
    ExecutionPlan,
)
from app.execution.execution_policy import (
    ExecutionPolicy,
    execution_policy,
)


class ExecutionValidator:
    """
    Última validação antes da criação
    de ordens reais.

    Regras verificadas:

    - aprovação do Pipeline;
    - aprovação do Portfolio;
    - aprovação do planejamento operacional;
    - nível de risco;
    - qualidade do match;
    - lucro e ROI;
    - preços;
    - stakes dos dois lados.
    """

    BLOCKED_RISK_LEVELS = {
        "HIGH",
        "CRITICAL",
    }

    MIN_MATCH_SCORE = 0.90

    @staticmethod
    def _read(
        target: Any,
        field: str,
        default: Any = None,
    ) -> Any:
        if isinstance(target, Mapping):
            return target.get(
                field,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field,
            default,
        )

    @classmethod
    def _nested(
        cls,
        target: Any,
        parent: str,
        child: str,
        default: Any = None,
    ) -> Any:
        parent_value = cls._read(
            target,
            parent,
            None,
        )

        return cls._read(
            parent_value,
            child,
            default,
        )

    @staticmethod
    def _number(
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

        if not isfinite(number):
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser finito."
            )

        return number

    @classmethod
    def _price(
        cls,
        opportunity: Any,
        leg: str,
    ) -> float:
        field_name = (
            f"{leg}_price"
        )

        value = cls._read(
            opportunity,
            field_name,
            None,
        )

        if value is None:
            value = cls._nested(
                opportunity,
                "prices",
                leg,
                None,
            )

        return cls._number(
            value,
            field_name,
        )

    @classmethod
    def _stake(
        cls,
        opportunity: Any,
        leg: str,
    ) -> float:
        value = cls._nested(
            opportunity,
            "stake",
            leg,
            None,
        )

        return cls._number(
            value,
            f"stake.{leg}",
        )

    @classmethod
    def _normalized_match_score(
        cls,
        opportunity: Any,
    ) -> float:
        value = cls._read(
            opportunity,
            "match_score",
            None,
        )

        if value is None:
            value = cls._read(
                opportunity,
                "similarity",
                None,
            )

        if value is None:
            value = cls._read(
                opportunity,
                "confidence",
                None,
            )

        score = cls._number(
            value,
            "match_score",
        )

        if score > 1:
            score /= 100

        return score

    def evaluate(
        self,
        opportunity: Any,
    ) -> dict[str, Any]:
        """
        Retorna a avaliação completa sem
        interromper o fluxo por dados inválidos.
        """

        reasons: list[str] = []
        values: dict[str, Any] = {}

        if opportunity is None:
            return {
                "approved": False,
                "executable": False,
                "reasons": [
                    "OPPORTUNITY_MISSING"
                ],
                "values": values,
            }

        pipeline_approved = self._read(
            opportunity,
            "approved",
            None,
        )

        if pipeline_approved is False:
            reasons.append(
                "PIPELINE_NOT_APPROVED"
            )

        portfolio_approved = self._nested(
            opportunity,
            "portfolio",
            "approved",
            False,
        )

        if not bool(portfolio_approved):
            reasons.append(
                "PORTFOLIO_NOT_APPROVED"
            )

        execution_approved = self._nested(
            opportunity,
            "execution",
            "approved",
            None,
        )

        if execution_approved is False:
            reasons.append(
                "EXECUTION_PLAN_REJECTED"
            )

        risk_level = str(
            self._nested(
                opportunity,
                "risk",
                "level",
                "UNKNOWN",
            )
        ).strip().upper()

        values["risk_level"] = (
            risk_level
        )

        if (
            risk_level
            in self.BLOCKED_RISK_LEVELS
        ):
            reasons.append(
                "RISK_BLOCKED"
            )

        try:
            match_score = (
                self._normalized_match_score(
                    opportunity
                )
            )

            values["match_score"] = (
                match_score
            )

            if (
                match_score
                < self.MIN_MATCH_SCORE
            ):
                reasons.append(
                    "MATCH_SCORE_LOW"
                )

        except (TypeError, ValueError):
            values["match_score"] = None

            reasons.append(
                "MATCH_SCORE_INVALID"
            )

        for field_name in (
            "profit",
            "roi",
        ):
            try:
                number = self._number(
                    self._read(
                        opportunity,
                        field_name,
                        None,
                    ),
                    field_name,
                )

                values[field_name] = number

                if number <= 0:
                    reasons.append(
                        f"{field_name.upper()}"
                        "_NOT_POSITIVE"
                    )

            except (TypeError, ValueError):
                values[field_name] = None

                reasons.append(
                    f"{field_name.upper()}"
                    "_INVALID"
                )

        for leg in (
            "yes",
            "no",
        ):
            try:
                price = self._price(
                    opportunity,
                    leg,
                )

                values[
                    f"{leg}_price"
                ] = price

                if not 0 < price <= 1:
                    reasons.append(
                        f"{leg.upper()}"
                        "_PRICE_INVALID"
                    )

            except (TypeError, ValueError):
                values[
                    f"{leg}_price"
                ] = None

                reasons.append(
                    f"{leg.upper()}"
                    "_PRICE_INVALID"
                )

            try:
                stake = self._stake(
                    opportunity,
                    leg,
                )

                values[
                    f"{leg}_stake"
                ] = stake

                if stake <= 0:
                    reasons.append(
                        f"{leg.upper()}"
                        "_STAKE_INVALID"
                    )

            except (TypeError, ValueError):
                values[
                    f"{leg}_stake"
                ] = None

                reasons.append(
                    f"{leg.upper()}"
                    "_STAKE_INVALID"
                )

        reasons = list(
            dict.fromkeys(reasons)
        )

        approved = not reasons

        return {
            "approved": approved,
            "executable": approved,
            "reasons": reasons,
            "values": values,
        }

    def validate(
        self,
        opportunity: Any,
    ) -> bool:
        """
        Interface booleana preservada.
        """

        return bool(
            self.evaluate(
                opportunity
            )["approved"]
        )

    def build_plan(
        self,
        opportunity: Any,
        *,
        policy: Mapping[str, Any] | None = None,
        policy_service: (
            ExecutionPolicy
            | None
        ) = None,
    ) -> ExecutionPlan:
        """
        Constrói um plano aprovado ou rejeitado.
        """

        evaluation = self.evaluate(
            opportunity
        )

        resolved_policy = dict(
            policy
            or (
                policy_service
                or execution_policy
            ).create(
                opportunity
            )
        )

        values = evaluation[
            "values"
        ]

        reasons = evaluation[
            "reasons"
        ]

        return ExecutionPlan(
            question=str(
                self._read(
                    opportunity,
                    "question",
                    "",
                )
                or ""
            ),
            yes_platform=str(
                self._read(
                    opportunity,
                    "buy_yes_platform",
                    "",
                )
                or ""
            ),
            no_platform=str(
                self._read(
                    opportunity,
                    "buy_no_platform",
                    "",
                )
                or ""
            ),
            yes_price=(
                values.get(
                    "yes_price"
                )
                or 0.0
            ),
            no_price=(
                values.get(
                    "no_price"
                )
                or 0.0
            ),
            yes_stake=(
                values.get(
                    "yes_stake"
                )
                or 0.0
            ),
            no_stake=(
                values.get(
                    "no_stake"
                )
                or 0.0
            ),
            expected_profit=(
                values.get(
                    "profit"
                )
                or 0.0
            ),
            estimated_roi=(
                values.get(
                    "roi"
                )
                or 0.0
            ),
            max_latency=(
                resolved_policy[
                    "max_latency"
                ]
            ),
            simultaneous=(
                resolved_policy[
                    "simultaneous"
                ]
            ),
            retry=(
                resolved_policy[
                    "retry"
                ]
            ),
            cancel_on_failure=(
                resolved_policy[
                    "cancel_on_failure"
                ]
            ),
            execute=(
                evaluation["approved"]
            ),
            reason=(
                "OK"
                if evaluation["approved"]
                else reasons[0]
            ),
            opportunity=opportunity,
            metadata={
                "validation": evaluation,
                "policy": resolved_policy,
            },
        )

    plan = build_plan


execution_validator = ExecutionValidator()