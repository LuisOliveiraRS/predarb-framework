from __future__ import annotations

from collections.abc import Iterable, Mapping
from decimal import Decimal, InvalidOperation
from typing import Any


_MISSING = object()


class StatisticsService:
    """
    Serviço de estatísticas básicas de trades.

    O método total_profit() preserva a interface
    pública original e soma o campo pnl de todos
    os trades.
    """

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
            "Trade sem o campo obrigatório "
            f"{field_name!r}."
        )

    @staticmethod
    def _to_decimal(
        value: Any,
        field_name: str,
    ) -> Decimal:
        """
        Converte valores financeiros para Decimal.
        """

        if isinstance(value, bool):
            raise TypeError(
                f"O campo {field_name!r} não pode "
                "ser booleano."
            )

        try:
            number = Decimal(
                str(value)
            )

        except (
            InvalidOperation,
            TypeError,
            ValueError,
        ) as exc:
            raise TypeError(
                f"O campo {field_name!r} deve "
                "ser numérico."
            ) from exc

        if not number.is_finite():
            raise ValueError(
                f"O campo {field_name!r} deve "
                "ser um número finito."
            )

        return number

    def _pnl_values(
        self,
        trades: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> list[Decimal]:
        """
        Extrai os valores de PnL dos trades.
        """

        if trades is None:
            return []

        if isinstance(
            trades,
            (str, bytes),
        ):
            raise TypeError(
                "Trades deve ser uma coleção."
            )

        values: list[Decimal] = []

        for trade in trades:
            try:
                pnl = self._read_field(
                    trade,
                    "pnl",
                )

                values.append(
                    self._to_decimal(
                        pnl,
                        "pnl",
                    )
                )

            except (TypeError, ValueError):
                if not ignore_invalid:
                    raise

        return values

    def total_profit(
        self,
        trades: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> float:
        """
        Retorna o lucro ou prejuízo total.

        Preserva a interface pública original.
        """

        pnl_values = self._pnl_values(
            trades,
            ignore_invalid=ignore_invalid,
        )

        total = sum(
            pnl_values,
            Decimal("0"),
        )

        return round(
            float(total),
            2,
        )

    def calculate(
        self,
        trades: Iterable[Any] | None,
        *,
        ignore_invalid: bool = False,
    ) -> dict[str, Any]:
        """
        Calcula um resumo estatístico dos trades.
        """

        pnl_values = self._pnl_values(
            trades,
            ignore_invalid=ignore_invalid,
        )

        total_trades = len(
            pnl_values,
        )

        total = sum(
            pnl_values,
            Decimal("0"),
        )

        profitable = [
            pnl
            for pnl in pnl_values
            if pnl > 0
        ]

        losing = [
            pnl
            for pnl in pnl_values
            if pnl < 0
        ]

        breakeven = [
            pnl
            for pnl in pnl_values
            if pnl == 0
        ]

        average = (
            total / Decimal(total_trades)
            if total_trades
            else Decimal("0")
        )

        win_rate = (
            Decimal(len(profitable))
            / Decimal(total_trades)
            * Decimal("100")
            if total_trades
            else Decimal("0")
        )

        max_profit = (
            max(pnl_values)
            if pnl_values
            else Decimal("0")
        )

        max_loss = (
            min(pnl_values)
            if pnl_values
            else Decimal("0")
        )

        gross_profit = sum(
            profitable,
            Decimal("0"),
        )

        gross_loss = abs(
            sum(
                losing,
                Decimal("0"),
            )
        )

        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else None
        )

        return {
            "trades": total_trades,
            "profitable_trades": len(
                profitable,
            ),
            "losing_trades": len(
                losing,
            ),
            "breakeven_trades": len(
                breakeven,
            ),
            "total_profit": round(
                float(total),
                2,
            ),
            "average_profit": round(
                float(average),
                2,
            ),
            "win_rate": round(
                float(win_rate),
                2,
            ),
            "max_profit": round(
                float(max_profit),
                2,
            ),
            "max_loss": round(
                float(max_loss),
                2,
            ),
            "gross_profit": round(
                float(gross_profit),
                2,
            ),
            "gross_loss": round(
                float(gross_loss),
                2,
            ),
            "profit_factor": (
                round(
                    float(profit_factor),
                    4,
                )
                if profit_factor is not None
                else None
            ),
        }

    summary = calculate


statistics_service = StatisticsService()