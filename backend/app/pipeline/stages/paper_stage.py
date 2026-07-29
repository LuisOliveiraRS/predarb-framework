from __future__ import annotations

from collections.abc import Mapping
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage


class PaperStage(PipelineStage):
    """
    Simula o preenchimento das intenções de ordem.

    O estágio não altera PaperWallet, posições ou
    histórico global. Essas responsabilidades serão
    tratadas durante a auditoria específica de Paper
    Trading e Portfolio.
    """

    def __init__(
        self,
        *,
        fee_rate: float = 0.0,
        strict: bool = False,
    ) -> None:
        self.fee_rate = (
            self._non_negative_number(
                fee_rate,
                "fee_rate",
            )
        )

        self.strict = bool(
            strict
        )

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(
            target,
            Mapping,
        ):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @staticmethod
    def _number(
        value: Any,
        field_name: str,
    ) -> float:
        if isinstance(
            value,
            bool,
        ):
            raise TypeError(
                f"O campo {field_name!r} "
                "não pode ser booleano."
            )

        try:
            number = float(
                value
            )

        except (
            TypeError,
            ValueError,
        ) as exc:
            raise TypeError(
                f"O campo {field_name!r} "
                "deve ser numérico."
            ) from exc

        if not isfinite(
            number
        ):
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser finito."
            )

        return number

    @classmethod
    def _positive_number(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        number = cls._number(
            value,
            field_name,
        )

        if number <= 0:
            raise ValueError(
                f"O campo {field_name!r} "
                "deve ser maior que zero."
            )

        return number

    @classmethod
    def _non_negative_number(
        cls,
        value: Any,
        field_name: str,
    ) -> float:
        number = cls._number(
            value,
            field_name,
        )

        if number < 0:
            raise ValueError(
                f"O campo {field_name!r} "
                "não pode ser negativo."
            )

        return number

    @classmethod
    def _orders_from_context(
        cls,
        context: Any,
    ) -> list[Any]:
        if context.orders is not None:
            return list(
                context.orders
            )

        orders: list[Any] = []

        for opportunity in list(
            context.opportunities
            or []
        ):
            opportunity_orders = (
                cls._read_field(
                    opportunity,
                    "orders",
                    [],
                )
            )

            if opportunity_orders:
                orders.extend(
                    list(
                        opportunity_orders
                    )
                )

        return orders

    def simulate_order(
        self,
        order: Any,
    ) -> dict[str, Any]:
        order_id = str(
            self._read_field(
                order,
                "id",
                "",
            )
        ).strip()

        if not order_id:
            raise ValueError(
                "A ordem não possui "
                "um ID válido."
            )

        raw_side = self._read_field(
            order,
            "side",
            "BUY",
        )
        side = str(
            getattr(raw_side, "value", raw_side)
        ).strip().upper()
        if "." in side:
            side = side.rsplit(".", 1)[-1]

        price = self._positive_number(
            self._read_field(
                order,
                "price",
                None,
            ),
            "price",
        )

        quantity = self._positive_number(
            self._read_field(
                order,
                "quantity",
                None,
            ),
            "quantity",
        )

        slippage_rate = (
            self._non_negative_number(
                self._read_field(
                    order,
                    "slippage_rate",
                    0.0,
                ),
                "slippage_rate",
            )
        )

        if side == "SELL":
            average_price = max(
                0.0,
                price
                * (
                    1.0
                    - slippage_rate
                ),
            )

        else:
            average_price = min(
                1.0,
                price
                * (
                    1.0
                    + slippage_rate
                ),
            )

        gross_notional = (
            quantity
            * average_price
        )

        fee = (
            gross_notional
            * self.fee_rate
        )

        return {
            "order_id": order_id,
            "platform": self._read_field(
                order,
                "platform",
                None,
            ),
            "symbol": self._read_field(
                order,
                "symbol",
                None,
            ),
            "leg": self._read_field(
                order,
                "leg",
                None,
            ),
            "side": side,
            "status": "FILLED",
            "requested_price": round(
                price,
                6,
            ),
            "average_price": round(
                average_price,
                6,
            ),
            "requested_quantity": round(
                quantity,
                8,
            ),
            "filled_quantity": round(
                quantity,
                8,
            ),
            "gross_notional": round(
                gross_notional,
                2,
            ),
            "fee": round(
                fee,
                2,
            ),
            "net_notional": round(
                gross_notional
                + fee,
                2,
            ),
            "slippage_rate": round(
                slippage_rate,
                6,
            ),
            "mode": "PAPER",
            "executed_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

    def process(
        self,
        context: Any,
    ) -> Any:
        orders = self._orders_from_context(
            context
        )

        reports: list[
            dict[str, Any]
        ] = []

        failures: list[
            dict[str, Any]
        ] = []

        for index, order in enumerate(
            orders
        ):
            try:
                reports.append(
                    self.simulate_order(
                        order
                    )
                )

            except (
                TypeError,
                ValueError,
            ) as exc:
                failures.append(
                    {
                        "index": index,
                        "order_id": (
                            self._read_field(
                                order,
                                "id",
                                None,
                            )
                        ),
                        "error": str(exc),
                    }
                )

                if self.strict:
                    raise

        total_fees = sum(
            float(
                report["fee"]
            )
            for report in reports
        )

        total_notional = sum(
            float(
                report[
                    "gross_notional"
                ]
            )
            for report in reports
        )

        summary = {
            "mode": "PAPER",
            "status": (
                "SUCCESS"
                if reports
                and not failures
                else "PARTIAL"
                if reports
                else "EMPTY"
                if not failures
                else "FAILED"
            ),
            "orders_received": len(
                orders
            ),
            "orders_filled": len(
                reports
            ),
            "orders_failed": len(
                failures
            ),
            "total_notional": round(
                total_notional,
                2,
            ),
            "total_fees": round(
                total_fees,
                2,
            ),
            "reports": reports,
            "failures": failures,
            "completed_at": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

        context.execution_reports = (
            reports
        )

        context.execution_report = (
            summary
        )

        context.metadata[
            "paper_execution"
        ] = {
            "status": summary["status"],
            "orders_received": len(
                orders
            ),
            "orders_filled": len(
                reports
            ),
            "orders_failed": len(
                failures
            ),
            "fee_rate": self.fee_rate,
        }

        return context

    execute = process