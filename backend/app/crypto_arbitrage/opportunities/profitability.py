"""Cálculo de lucratividade líquida.

Seção 15 do CLAUDE.md. A regra que este módulo existe para
impor: **não comparar last price**. Preço executável se calcula
por profundidade, e a diferença entre topo de livro e VWAP é
justamente onde a maioria das "oportunidades" desaparece.

A fórmula desconta taxas efetivas, reserva de slippage e buffer
operacional. Ainda assim o resultado é uma **expectativa**, não
uma promessa: latência, fill parcial, falha de API e movimento de
mercado continuam podendo transformar lucro esperado em prejuízo
realizado.

Nenhum custo é presumido. Taxa desconhecida levanta erro em vez
de virar zero, conforme a invariante 15 da seção 8.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from app.crypto_arbitrage.domain.errors import (
    DomainValidationError,
)
from app.crypto_arbitrage.domain.fees import FeeSchedule
from app.crypto_arbitrage.domain.money import (
    ZERO,
    DecimalInput,
    ensure_non_negative,
    ensure_positive,
    ensure_rate,
)


@dataclass(frozen=True, slots=True)
class CostModel:
    """Parâmetros de custo aplicados sobre toda oportunidade.

    `slippage_ratio` e `safety_buffer_ratio` incidem sobre o
    notional negociado, não sobre o lucro: são reservas contra
    execução pior que a esperada, e o tamanho do risco acompanha
    o tamanho da posição, não o do ganho projetado.
    """

    slippage_ratio: Decimal
    safety_buffer_ratio: Decimal
    minimum_net_profit: Decimal
    minimum_roi: Decimal

    @classmethod
    def create(
        cls,
        *,
        slippage_ratio: DecimalInput = "0.0005",
        safety_buffer_ratio: DecimalInput = "0.0005",
        minimum_net_profit: DecimalInput = "0",
        minimum_roi: DecimalInput = "0",
    ) -> "CostModel":
        return cls(
            slippage_ratio=ensure_rate(
                slippage_ratio,
                field_name="slippage_ratio",
            ),
            safety_buffer_ratio=ensure_rate(
                safety_buffer_ratio,
                field_name="safety_buffer_ratio",
            ),
            minimum_net_profit=ensure_non_negative(
                minimum_net_profit,
                field_name="minimum_net_profit",
            ),
            minimum_roi=ensure_rate(
                minimum_roi,
                field_name="minimum_roi",
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "slippage_ratio": str(self.slippage_ratio),
            "safety_buffer_ratio": str(
                self.safety_buffer_ratio
            ),
            "minimum_net_profit": str(
                self.minimum_net_profit
            ),
            "minimum_roi": str(self.minimum_roi),
        }


@dataclass(frozen=True, slots=True)
class ProfitBreakdown:
    """Decomposição completa do cálculo.

    Guardar cada parcela, e não só o total, é o que permite
    responder depois por que uma oportunidade foi descartada — ou
    por que o resultado realizado divergiu do esperado.
    """

    quantity: Decimal
    buy_vwap: Decimal
    sell_vwap: Decimal
    buy_cost: Decimal
    sell_proceeds: Decimal
    gross_profit: Decimal
    buy_fee: Decimal
    sell_fee: Decimal
    slippage_reserve: Decimal
    safety_buffer: Decimal
    expected_net_profit: Decimal
    expected_roi: Decimal

    @property
    def total_fees(self) -> Decimal:
        return self.buy_fee + self.sell_fee

    @property
    def total_reserves(self) -> Decimal:
        return self.slippage_reserve + self.safety_buffer

    @property
    def is_profitable(self) -> bool:
        return self.expected_net_profit > ZERO

    def to_dict(self) -> dict[str, Any]:
        return {
            "quantity": str(self.quantity),
            "buy_vwap": str(self.buy_vwap),
            "sell_vwap": str(self.sell_vwap),
            "buy_cost": str(self.buy_cost),
            "sell_proceeds": str(self.sell_proceeds),
            "gross_profit": str(self.gross_profit),
            "buy_fee": str(self.buy_fee),
            "sell_fee": str(self.sell_fee),
            "total_fees": str(self.total_fees),
            "slippage_reserve": str(
                self.slippage_reserve
            ),
            "safety_buffer": str(self.safety_buffer),
            "total_reserves": str(self.total_reserves),
            "expected_net_profit": str(
                self.expected_net_profit
            ),
            "expected_roi": str(self.expected_roi),
            "is_profitable": self.is_profitable,
        }


def compute_breakdown(
    *,
    quantity: DecimalInput,
    buy_vwap: DecimalInput,
    sell_vwap: DecimalInput,
    buy_fee_rate: DecimalInput,
    sell_fee_rate: DecimalInput,
    cost_model: CostModel,
) -> ProfitBreakdown:
    """Aplica a fórmula da seção 15 sobre preços executáveis.

    Espera VWAPs, não topo de livro. Passar melhor bid e melhor
    ask aqui produziria um número otimista que a execução não
    reproduz.
    """

    amount = ensure_positive(
        quantity,
        field_name="quantity",
    )

    buy_price = ensure_positive(
        buy_vwap,
        field_name="buy_vwap",
    )

    sell_price = ensure_positive(
        sell_vwap,
        field_name="sell_vwap",
    )

    buy_rate = ensure_rate(
        buy_fee_rate,
        field_name="buy_fee_rate",
    )

    sell_rate = ensure_rate(
        sell_fee_rate,
        field_name="sell_fee_rate",
    )

    buy_cost = buy_price * amount
    sell_proceeds = sell_price * amount
    gross_profit = sell_proceeds - buy_cost

    buy_fee = buy_cost * buy_rate
    sell_fee = sell_proceeds * sell_rate

    traded_notional = buy_cost + sell_proceeds

    slippage_reserve = (
        traded_notional * cost_model.slippage_ratio
    )

    safety_buffer = (
        traded_notional * cost_model.safety_buffer_ratio
    )

    expected_net_profit = (
        gross_profit
        - buy_fee
        - sell_fee
        - slippage_reserve
        - safety_buffer
    )

    expected_roi = (
        expected_net_profit / buy_cost
        if buy_cost > ZERO
        else ZERO
    )

    return ProfitBreakdown(
        quantity=amount,
        buy_vwap=buy_price,
        sell_vwap=sell_price,
        buy_cost=buy_cost,
        sell_proceeds=sell_proceeds,
        gross_profit=gross_profit,
        buy_fee=buy_fee,
        sell_fee=sell_fee,
        slippage_reserve=slippage_reserve,
        safety_buffer=safety_buffer,
        expected_net_profit=expected_net_profit,
        expected_roi=expected_roi,
    )


def meets_thresholds(
    breakdown: ProfitBreakdown,
    cost_model: CostModel,
) -> tuple[bool, str]:
    """Confere lucro e ROI mínimos, devolvendo o motivo."""

    if breakdown.expected_net_profit <= ZERO:
        return (
            False,
            "Lucro líquido esperado não é positivo após "
            "taxas e reservas.",
        )

    if (
        breakdown.expected_net_profit
        < cost_model.minimum_net_profit
    ):
        return (
            False,
            "Lucro líquido "
            f"{breakdown.expected_net_profit} abaixo do "
            f"mínimo {cost_model.minimum_net_profit}.",
        )

    if breakdown.expected_roi < cost_model.minimum_roi:
        return (
            False,
            f"ROI {breakdown.expected_roi} abaixo do "
            f"mínimo {cost_model.minimum_roi}.",
        )

    return (True, "Dentro dos limites configurados.")


def resolve_taker_rates(
    schedule: FeeSchedule,
    *,
    buy_venue_id: str,
    buy_instrument_id: str,
    sell_venue_id: str,
    sell_instrument_id: str,
    moment: datetime | None = None,
) -> tuple[Decimal, Decimal]:
    """Busca as taxas taker das duas pernas.

    Levanta `FeeUnknownError` se qualquer uma faltar. Arbitragem
    entre venues usa taker nas duas pontas por padrão: contar com
    maker exige repousar ordem no livro, e o preço pode sumir
    antes do fill.
    """

    if not str(buy_venue_id).strip():
        raise DomainValidationError(
            "buy_venue_id é obrigatório."
        )

    if not str(sell_venue_id).strip():
        raise DomainValidationError(
            "sell_venue_id é obrigatório."
        )

    buy_rate = schedule.taker_rate(
        buy_venue_id,
        buy_instrument_id,
        moment=moment,
    )

    sell_rate = schedule.taker_rate(
        sell_venue_id,
        sell_instrument_id,
        moment=moment,
    )

    return (buy_rate, sell_rate)
