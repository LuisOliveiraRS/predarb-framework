"""Enumerações do domínio cripto.

Todas herdam de `str` para serializar direto em JSON sem conversão
manual, seguindo o padrão já usado nos payloads do PredArb.
"""

from __future__ import annotations

from enum import Enum


class VenueKind(str, Enum):
    """Natureza da venue, que determina o modelo de execução."""

    CEX = "CEX"
    DEX = "DEX"


class MarketType(str, Enum):
    SPOT = "SPOT"
    PERPETUAL = "PERPETUAL"
    FUTURE = "FUTURE"


class InstrumentStatus(str, Enum):
    """Status operacional do instrumento na venue.

    `UNKNOWN` é o default deliberado: instrumento sem status
    confirmado não é negociável.
    """

    UNKNOWN = "UNKNOWN"
    TRADING = "TRADING"
    HALTED = "HALTED"
    DELISTED = "DELISTED"


class Side(str, Enum):
    BUY = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    LIMIT = "LIMIT"
    MARKET = "MARKET"


class TimeInForce(str, Enum):
    GTC = "GTC"
    IOC = "IOC"
    FOK = "FOK"


class StrategyType(str, Enum):
    CEX_CEX_SPATIAL = "CEX_CEX_SPATIAL"
    TRIANGULAR = "TRIANGULAR"
    CEX_DEX = "CEX_DEX"
    DEX_DEX = "DEX_DEX"
    SPOT_PERP = "SPOT_PERP"


class RiskStatus(str, Enum):
    """Decisão de risco sobre uma oportunidade.

    `BLOCKED` é o default de toda oportunidade recém-criada.
    Nada se torna elegível sem avaliação explícita.
    """

    BLOCKED = "BLOCKED"
    REVIEW = "REVIEW"
    ELIGIBLE = "ELIGIBLE"


class ExecutionMode(str, Enum):
    """Modo de execução de um plano.

    `LIVE` existe apenas como valor declarado. A Fase 18 não
    possui caminho de código capaz de produzir execução real.
    """

    PAPER = "PAPER"
    SHADOW = "SHADOW"
    TESTNET = "TESTNET"
    LIVE = "LIVE"


class ConnectorState(str, Enum):
    """Estado de saúde de um conector de dados.

    Apenas `READY` habilita uso do book em cálculo de
    oportunidade. Qualquer outro estado é fail-closed.
    """

    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    READY = "READY"
    DEGRADED = "DEGRADED"
    STALE = "STALE"

    @property
    def is_usable(self) -> bool:
        return self is ConnectorState.READY
