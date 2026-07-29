from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

from app.pipeline.pipeline_context import (
    PipelineContext,
)
from app.pipeline.stages.validator_stage import (
    ValidatorStage,
)


class OpportunityValidator:
    """
    Fachada de compatibilidade para o
    ValidatorStage oficial.
    """

    REQUIRED_FIELDS = [
        "question",
        "buy_yes_platform",
        "buy_no_platform",
        "yes_price",
        "no_price",
        "cost",
        "profit",
        "roi",
    ]

    def __init__(
        self,
        *,
        strict: bool = False,
    ) -> None:
        self.strict = bool(strict)
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _as_list(
        opportunities: Any,
    ) -> list[Any]:
        if opportunities is None:
            return []

        if isinstance(
            opportunities,
            Mapping,
        ):
            return [opportunities]

        if isinstance(
            opportunities,
            (str, bytes),
        ):
            raise TypeError(
                "opportunities deve ser "
                "uma coleção."
            )

        if isinstance(
            opportunities,
            Iterable,
        ):
            return list(
                opportunities
            )

        return [opportunities]

    def validate_one(
        self,
        opportunity: Any,
    ) -> list[str]:
        """
        Retorna os problemas de uma
        única oportunidade.
        """

        stage = ValidatorStage(
            strict=False
        )

        return stage.validate_opportunity(
            opportunity
        )

    def validate(
        self,
        opportunities: Any,
        *,
        strict: bool | None = None,
    ) -> list[Any]:
        """
        Valida uma coleção utilizando
        a regra oficial do Pipeline.
        """

        resolved_strict = (
            self.strict
            if strict is None
            else bool(strict)
        )

        context = PipelineContext(
            {
                "opportunities": self._as_list(
                    opportunities
                ),
            }
        )

        ValidatorStage(
            strict=resolved_strict
        ).process(context)

        self.last_report = dict(
            context.metadata.get(
                "validation",
                {},
            )
        )

        return list(
            context.opportunities
            or []
        )


opportunity_validator = OpportunityValidator()