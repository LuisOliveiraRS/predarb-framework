from __future__ import annotations

from collections.abc import Mapping
from math import isfinite
from typing import Any


_MISSING = object()


class ExecutionService:
    """
    Serviço de decisão preliminar de execução.

    Regras preservadas:

    - expected_profit deve ser maior que zero;
    - risk.level não pode ser HIGH.

    Este serviço não executa ordens. Ele apenas
    informa se uma oportunidade pode avançar para
    a camada oficial de Execution/OMS.
    """

    BLOCKED_RISK_LEVELS = {
        "HIGH",
    }

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = _MISSING,
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

        if default is not _MISSING:
            return default

        raise ValueError(
            "Objeto sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _to_number(
        value: Any,
        field_name: str,
    ) -> float:
        """
        Converte e valida um valor numérico.
        """

        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} não pode "
                "ser booleano."
            )

        try:
            number = float(value)

        except (TypeError, ValueError) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve "
                "ser numérico."
            ) from exc

        if not isfinite(number):
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser um número finito."
            )

        return number

    def _risk_level(
        self,
        risk: Any,
    ) -> str:
        """
        Recupera e normaliza o nível de risco.
        """

        if isinstance(risk, str):
            level = risk

        else:
            level = self._read_field(
                risk,
                "level",
            )

        if not isinstance(level, str):
            raise TypeError(
                "O nível de risco deve ser uma string."
            )

        normalized = level.strip().upper()

        if not normalized:
            raise ValueError(
                "O nível de risco não pode ser vazio."
            )

        return normalized

    def evaluate(
        self,
        opportunity: Any,
        *,
        strict: bool = False,
    ) -> dict[str, Any]:
        """
        Avalia uma oportunidade e retorna as razões
        de aprovação ou bloqueio.

        Quando strict=False, dados inválidos produzem
        uma decisão negativa em vez de interromper
        o fluxo de execução.
        """

        try:
            if opportunity is None:
                raise ValueError(
                    "A oportunidade não pode ser None."
                )

            expected_profit = self._to_number(
                self._read_field(
                    opportunity,
                    "expected_profit",
                ),
                "expected_profit",
            )

            risk = self._read_field(
                opportunity,
                "risk",
            )

            risk_level = self._risk_level(
                risk,
            )

        except (TypeError, ValueError) as exc:
            if strict:
                raise

            return {
                "executable": False,
                "expected_profit": None,
                "risk_level": None,
                "reasons": [
                    str(exc),
                ],
            }

        reasons: list[str] = []

        if expected_profit <= 0:
            reasons.append(
                "O lucro esperado deve ser maior "
                "que zero."
            )

        if risk_level in self.BLOCKED_RISK_LEVELS:
            reasons.append(
                f"Nível de risco bloqueado: {risk_level}."
            )

        return {
            "executable": not reasons,
            "expected_profit": expected_profit,
            "risk_level": risk_level,
            "reasons": reasons,
        }

    def executable(
        self,
        opportunity: Any,
        *,
        strict: bool = False,
    ) -> bool:
        """
        Indica se uma oportunidade pode avançar
        para execução.

        Preserva a interface pública original.
        """

        evaluation = self.evaluate(
            opportunity,
            strict=strict,
        )

        return bool(
            evaluation["executable"]
        )

    is_executable = executable


execution_service = ExecutionService()