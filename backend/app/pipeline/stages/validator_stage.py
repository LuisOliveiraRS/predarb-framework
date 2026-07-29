from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


_NOT_FOUND = object()


class ValidatorStage(PipelineStage):
    """
    Valida a estrutura das oportunidades recebidas
    pelo Pipeline.

    Formatos de preços aceitos:

        {
            "yes_price": 0.45,
            "no_price": 0.45,
            "cost": 0.90
        }

    ou:

        {
            "prices": {
                "yes": 0.45,
                "no": 0.45
            },
            "stake": {
                "total": 0.90
            }
        }
    """

    REQUIRED_TEXT_FIELDS = (
        "question",
        "buy_yes_platform",
        "buy_no_platform",
    )

    def __init__(
        self,
        *,
        strict: bool = False,
    ) -> None:
        self.strict = bool(strict)

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = _NOT_FOUND,
    ) -> Any:
        """
        Recupera um campo de dicionário ou objeto.
        """

        if isinstance(target, Mapping):
            if field_name in target:
                return target[field_name]

        elif target is not None and hasattr(
            target,
            field_name,
        ):
            return getattr(
                target,
                field_name,
            )

        if default is not _NOT_FOUND:
            return default

        raise ValueError(
            f"Campo obrigatório ausente: {field_name}."
        )

    @classmethod
    def _read_nested(
        cls,
        target: Any,
        parent_name: str,
        child_name: str,
        default: Any = _NOT_FOUND,
    ) -> Any:
        """
        Recupera um campo aninhado.
        """

        parent = cls._read_field(
            target,
            parent_name,
            None,
        )

        if parent is None:
            if default is not _NOT_FOUND:
                return default

            raise ValueError(
                "Campo obrigatório ausente: "
                f"{parent_name}.{child_name}."
            )

        return cls._read_field(
            parent,
            child_name,
            default,
        )

    @staticmethod
    def _to_number(
        value: Any,
        field_name: str,
    ) -> float:
        """
        Converte e valida um campo numérico.
        """

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
                "deve ser um número finito."
            )

        return number

    @classmethod
    def _resolve_prices(
        cls,
        opportunity: Any,
    ) -> tuple[float, float]:
        """
        Recupera os preços Yes e No.
        """

        yes_price = cls._read_field(
            opportunity,
            "yes_price",
            None,
        )

        if yes_price is None:
            yes_price = cls._read_nested(
                opportunity,
                "prices",
                "yes",
                None,
            )

        no_price = cls._read_field(
            opportunity,
            "no_price",
            None,
        )

        if no_price is None:
            no_price = cls._read_nested(
                opportunity,
                "prices",
                "no",
                None,
            )

        if yes_price is None:
            raise ValueError(
                "Campo obrigatório ausente: yes_price."
            )

        if no_price is None:
            raise ValueError(
                "Campo obrigatório ausente: no_price."
            )

        return (
            cls._to_number(
                yes_price,
                "yes_price",
            ),
            cls._to_number(
                no_price,
                "no_price",
            ),
        )

    @classmethod
    def _resolve_cost(
        cls,
        opportunity: Any,
        yes_price: float,
        no_price: float,
    ) -> float:
        """
        Recupera ou calcula o custo da oportunidade.
        """

        cost = cls._read_field(
            opportunity,
            "cost",
            None,
        )

        if cost is None:
            cost = cls._read_nested(
                opportunity,
                "stake",
                "total",
                None,
            )

        if cost is None:
            cost = yes_price + no_price

        return cls._to_number(
            cost,
            "cost",
        )

    def validate_opportunity(
        self,
        opportunity: Any,
    ) -> list[str]:
        """
        Retorna os problemas encontrados em uma
        oportunidade.
        """

        if opportunity is None:
            return [
                "A oportunidade não pode ser None.",
            ]

        errors: list[str] = []

        for field_name in self.REQUIRED_TEXT_FIELDS:
            value = self._read_field(
                opportunity,
                field_name,
                None,
            )

            if (
                not isinstance(value, str)
                or not value.strip()
            ):
                errors.append(
                    f"Campo textual inválido: {field_name}."
                )

        yes_price: float | None = None
        no_price: float | None = None

        try:
            yes_price, no_price = self._resolve_prices(
                opportunity,
            )

            if not 0 <= yes_price <= 1:
                errors.append(
                    "yes_price deve estar entre 0 e 1."
                )

            if not 0 <= no_price <= 1:
                errors.append(
                    "no_price deve estar entre 0 e 1."
                )

        except (TypeError, ValueError) as exc:
            errors.append(str(exc))

        if (
            yes_price is not None
            and no_price is not None
        ):
            try:
                cost = self._resolve_cost(
                    opportunity,
                    yes_price,
                    no_price,
                )

                if cost <= 0:
                    errors.append(
                        "O custo deve ser maior que zero."
                    )

            except (TypeError, ValueError) as exc:
                errors.append(str(exc))

        for field_name in (
            "profit",
            "roi",
        ):
            value = self._read_field(
                opportunity,
                field_name,
                None,
            )

            if value is None:
                errors.append(
                    f"Campo obrigatório ausente: {field_name}."
                )
                continue

            try:
                self._to_number(
                    value,
                    field_name,
                )

            except (TypeError, ValueError) as exc:
                errors.append(str(exc))

        return errors

    def process(
        self,
        context: Any,
    ) -> Any:
        """
        Valida todas as oportunidades presentes
        no contexto.
        """

        opportunities = list(
            context.opportunities or []
        )

        valid: list[Any] = []
        invalid: list[dict[str, Any]] = []

        for index, opportunity in enumerate(
            opportunities
        ):
            errors = self.validate_opportunity(
                opportunity,
            )

            if not errors:
                valid.append(opportunity)
                continue

            invalid.append(
                {
                    "index": index,
                    "errors": errors,
                }
            )

            if self.strict:
                raise ValueError(
                    "Oportunidade inválida no índice "
                    f"{index}: {'; '.join(errors)}"
                )

        context.opportunities = valid

        context.metadata["validation"] = {
            "input": len(opportunities),
            "valid": len(valid),
            "invalid": len(invalid),
            "details": invalid,
        }

        return context

    execute = process
