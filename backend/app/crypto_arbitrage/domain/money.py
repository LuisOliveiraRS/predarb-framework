"""Aritmética financeira em Decimal.

Seção 28 do CLAUDE.md: nunca usar float para preço, quantidade,
taxa, PnL ou saldo. Este módulo recusa float ativamente em vez de
convertê-lo, porque a conversão silenciosa é justamente o que
introduz erro de representação em valores financeiros.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN, ROUND_UP

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
    PrecisionError,
)


ZERO = Decimal("0")

DecimalInput = Decimal | int | str


def to_decimal(
    value: DecimalInput,
    *,
    field_name: str = "valor",
) -> Decimal:
    """Converte para Decimal aceitando apenas tipos exatos.

    `float` é recusado de propósito: `0.1 + 0.2` já não é `0.3`, e
    um erro de representação num preço se propaga por VWAP, taxas
    e PnL sem deixar rastro.
    """

    if isinstance(value, bool):
        raise DomainValidationError(
            f"{field_name} não pode ser booleano."
        )

    if isinstance(value, float):
        raise PrecisionError(
            f"{field_name} não aceita float. "
            "Use Decimal, int ou str."
        )

    if isinstance(value, Decimal):
        decimal_value = value
    elif isinstance(value, (int, str)):
        try:
            decimal_value = Decimal(str(value).strip())
        except (InvalidOperation, ValueError) as exc:
            raise DomainValidationError(
                f"{field_name} não é um número válido."
            ) from exc
    else:
        raise DomainValidationError(
            f"{field_name} tem tipo não suportado: "
            f"{type(value).__name__}."
        )

    if not decimal_value.is_finite():
        raise DomainValidationError(
            f"{field_name} deve ser finito."
        )

    return decimal_value


def ensure_positive(
    value: DecimalInput,
    *,
    field_name: str = "valor",
) -> Decimal:
    decimal_value = to_decimal(
        value,
        field_name=field_name,
    )

    if decimal_value <= ZERO:
        raise DomainValidationError(
            f"{field_name} deve ser maior que zero."
        )

    return decimal_value


def ensure_non_negative(
    value: DecimalInput,
    *,
    field_name: str = "valor",
) -> Decimal:
    decimal_value = to_decimal(
        value,
        field_name=field_name,
    )

    if decimal_value < ZERO:
        raise DomainValidationError(
            f"{field_name} não pode ser negativo."
        )

    return decimal_value


def ensure_rate(
    value: DecimalInput,
    *,
    field_name: str = "taxa",
) -> Decimal:
    """Valida uma taxa expressa em fração, não em porcentagem.

    `0.001` significa 0,1%. O limite superior de 1 evita que uma
    taxa informada em porcentagem (`0.1` para 0,1%) passe
    despercebida como 10%.
    """

    decimal_value = ensure_non_negative(
        value,
        field_name=field_name,
    )

    if decimal_value > Decimal("1"):
        raise DomainValidationError(
            f"{field_name} deve ser uma fração entre 0 e 1."
        )

    return decimal_value


def quantize_down(
    value: DecimalInput,
    step: DecimalInput,
    *,
    field_name: str = "valor",
) -> Decimal:
    """Arredonda para baixo em múltiplos de `step`.

    Usado em quantidade a comprar ou vender: arredondar para baixo
    é sempre o lado conservador, porque nunca pede mais do que a
    profundidade ou o saldo comportam.
    """

    decimal_value = ensure_non_negative(
        value,
        field_name=field_name,
    )

    decimal_step = ensure_positive(
        step,
        field_name="step",
    )

    multiples = (
        decimal_value / decimal_step
    ).to_integral_value(rounding=ROUND_DOWN)

    return multiples * decimal_step


def quantize_up(
    value: DecimalInput,
    step: DecimalInput,
    *,
    field_name: str = "valor",
) -> Decimal:
    """Arredonda para cima em múltiplos de `step`.

    Usado em custo estimado, onde superestimar é o lado
    conservador.
    """

    decimal_value = ensure_non_negative(
        value,
        field_name=field_name,
    )

    decimal_step = ensure_positive(
        step,
        field_name="step",
    )

    multiples = (
        decimal_value / decimal_step
    ).to_integral_value(rounding=ROUND_UP)

    return multiples * decimal_step
