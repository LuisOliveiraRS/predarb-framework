from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any, Mapping


def _number(
    value: Any,
    *,
    default: float = 0.0,
) -> float:
    """
    Converte um valor em número finito.
    """

    if value is None or isinstance(
        value,
        bool,
    ):
        return float(default)

    try:
        number = float(value)

    except (TypeError, ValueError):
        return float(default)

    if not isfinite(number):
        return float(default)

    return number


def _probability(
    value: Any,
    field_name: str,
) -> float:
    """
    Valida um preço probabilístico.
    """

    if isinstance(value, bool):
        raise TypeError(
            f"O campo {field_name!r} "
            "não pode ser booleano."
        )

    try:
        probability = float(value)

    except (TypeError, ValueError) as exc:
        raise TypeError(
            f"O campo {field_name!r} "
            "deve ser numérico."
        ) from exc

    if not isfinite(probability):
        raise ValueError(
            f"O campo {field_name!r} "
            "deve ser finito."
        )

    if not 0 <= probability <= 1:
        raise ValueError(
            f"O campo {field_name!r} "
            "deve estar entre 0 e 1."
        )

    return probability


def _datetime_value(
    value: Any,
) -> datetime:
    """
    Converte datetime ou string ISO-8601.
    """

    if value is None:
        return datetime.now(
            timezone.utc,
        )

    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(
                tzinfo=timezone.utc,
            )

        return value

    if isinstance(value, str):
        normalized = value.strip()

        if not normalized:
            return datetime.now(
                timezone.utc,
            )

        if normalized.endswith("Z"):
            normalized = (
                normalized[:-1]
                + "+00:00"
            )

        try:
            parsed = datetime.fromisoformat(
                normalized
            )

        except ValueError as exc:
            raise ValueError(
                "created_at não possui "
                "uma data ISO-8601 válida."
            ) from exc

        if parsed.tzinfo is None:
            parsed = parsed.replace(
                tzinfo=timezone.utc,
            )

        return parsed

    raise TypeError(
        "created_at deve ser datetime "
        "ou string ISO-8601."
    )


@dataclass(slots=True)
class RiskResult:
    """
    Resultado oficial da análise de risco.
    """

    score: float = 0.0
    level: str = "LOW"
    reasons: list[str] = field(
        default_factory=list
    )

    def __post_init__(self) -> None:
        self.score = round(
            max(
                0.0,
                min(
                    100.0,
                    _number(
                        self.score,
                    ),
                ),
            ),
            2,
        )

        self.level = (
            str(self.level)
            .strip()
            .upper()
            or "LOW"
        )

        self.reasons = [
            str(reason)
            for reason in self.reasons
        ]

    @classmethod
    def from_value(
        cls,
        value: Any,
    ) -> RiskResult:
        if isinstance(value, cls):
            return value

        if isinstance(value, Mapping):
            return cls(
                score=value.get(
                    "score",
                    0.0,
                ),
                level=value.get(
                    "level",
                    "LOW",
                ),
                reasons=list(
                    value.get(
                        "reasons",
                        [],
                    )
                    or []
                ),
            )

        return cls()

    def to_dict(self) -> dict[str, Any]:
        return {
            "score": self.score,
            "level": self.level,
            "reasons": list(
                self.reasons
            ),
        }


@dataclass(slots=True)
class StakeResult:
    """
    Resultado oficial da distribuição de stake.

    Mantém compatibilidade com os campos antigos:

        amount
        expected_profit
        bankroll_percentage

    e com os campos canônicos:

        total
        guaranteed_profit
        yes
        no
    """

    amount: float = 0.0
    expected_profit: float = 0.0
    bankroll_percentage: float = 0.0

    bankroll: float = 0.0
    yes: float = 0.0
    no: float = 0.0
    guaranteed_return: float = 0.0

    def __post_init__(self) -> None:
        self.amount = round(
            max(
                0.0,
                _number(
                    self.amount,
                ),
            ),
            2,
        )

        self.expected_profit = round(
            _number(
                self.expected_profit,
            ),
            2,
        )

        self.bankroll_percentage = round(
            max(
                0.0,
                _number(
                    self.bankroll_percentage,
                ),
            ),
            4,
        )

        self.bankroll = round(
            max(
                0.0,
                _number(
                    self.bankroll,
                ),
            ),
            2,
        )

        self.yes = round(
            max(
                0.0,
                _number(
                    self.yes,
                ),
            ),
            2,
        )

        self.no = round(
            max(
                0.0,
                _number(
                    self.no,
                ),
            ),
            2,
        )

        self.guaranteed_return = round(
            max(
                0.0,
                _number(
                    self.guaranteed_return,
                ),
            ),
            2,
        )

    @property
    def total(self) -> float:
        return self.amount

    @total.setter
    def total(
        self,
        value: Any,
    ) -> None:
        self.amount = round(
            max(
                0.0,
                _number(value),
            ),
            2,
        )

    @property
    def guaranteed_profit(self) -> float:
        return self.expected_profit

    @guaranteed_profit.setter
    def guaranteed_profit(
        self,
        value: Any,
    ) -> None:
        self.expected_profit = round(
            _number(value),
            2,
        )

    @classmethod
    def from_value(
        cls,
        value: Any,
    ) -> StakeResult:
        if isinstance(value, cls):
            return value

        if not isinstance(value, Mapping):
            return cls()

        amount = value.get(
            "amount",
            value.get(
                "total",
                0.0,
            ),
        )

        expected_profit = value.get(
            "expected_profit",
            value.get(
                "guaranteed_profit",
                value.get(
                    "profit",
                    0.0,
                ),
            ),
        )

        bankroll = _number(
            value.get(
                "bankroll",
                0.0,
            )
        )

        percentage = value.get(
            "bankroll_percentage",
            None,
        )

        if percentage is None:
            percentage = (
                _number(amount)
                / bankroll
                * 100
                if bankroll > 0
                else 0.0
            )

        return cls(
            amount=amount,
            expected_profit=expected_profit,
            bankroll_percentage=percentage,
            bankroll=bankroll,
            yes=value.get(
                "yes",
                0.0,
            ),
            no=value.get(
                "no",
                0.0,
            ),
            guaranteed_return=value.get(
                "guaranteed_return",
                value.get(
                    "return",
                    0.0,
                ),
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "amount": self.amount,
            "total": self.total,
            "expected_profit": (
                self.expected_profit
            ),
            "guaranteed_profit": (
                self.guaranteed_profit
            ),
            "bankroll_percentage": (
                self.bankroll_percentage
            ),
            "bankroll": self.bankroll,
            "yes": self.yes,
            "no": self.no,
            "guaranteed_return": (
                self.guaranteed_return
            ),
        }


@dataclass(slots=True)
class Opportunity:
    """
    Modelo oficial de uma oportunidade
    de arbitragem.

    O modelo suporta acesso por atributo:

        opportunity.profit

    e acesso legado por chave:

        opportunity["profit"]
    """

    question: str

    buy_yes_platform: str
    buy_no_platform: str

    yes_price: float
    no_price: float

    cost: float
    profit: float
    roi: float

    edge: float = 0.0
    spread: float = 0.0

    expected_return: float = 0.0
    breakeven: float = 0.0

    confidence: float = 0.0
    match_score: float = 0.0

    risk: RiskResult = field(
        default_factory=RiskResult
    )

    stake: StakeResult = field(
        default_factory=StakeResult
    )

    score: float = 0.0
    approved: bool = False

    created_at: datetime | None = None

    opportunity_id: str = ""
    market_id: str = ""

    matched_question: str = ""

    platforms: list[str] = field(
        default_factory=list
    )

    connector_yes: str = ""
    connector_no: str = ""

    volume_yes: float = 0.0
    volume_no: float = 0.0

    liquidity_yes: float = 0.0
    liquidity_no: float = 0.0

    liquidity: dict[str, Any] = field(
        default_factory=dict
    )

    slippage: dict[str, Any] = field(
        default_factory=dict
    )

    portfolio: dict[str, Any] = field(
        default_factory=dict
    )

    market_yes: Any = None
    market_no: Any = None

    orders: list[Any] = field(
        default_factory=list
    )

    adjusted_profit: float | None = None
    adjusted_roi: float | None = None

    metadata: dict[str, Any] = field(
        default_factory=dict
    )

    def __post_init__(self) -> None:
        self.question = (
            str(self.question).strip()
        )

        self.buy_yes_platform = (
            str(
                self.buy_yes_platform
            ).strip()
        )

        self.buy_no_platform = (
            str(
                self.buy_no_platform
            ).strip()
        )

        if not self.question:
            raise ValueError(
                "A pergunta da oportunidade "
                "não pode ser vazia."
            )

        if not self.buy_yes_platform:
            raise ValueError(
                "buy_yes_platform não "
                "pode ser vazio."
            )

        if not self.buy_no_platform:
            raise ValueError(
                "buy_no_platform não "
                "pode ser vazio."
            )

        self.yes_price = _probability(
            self.yes_price,
            "yes_price",
        )

        self.no_price = _probability(
            self.no_price,
            "no_price",
        )

        self.cost = _number(
            self.cost,
        )

        self.profit = _number(
            self.profit,
        )

        self.roi = _number(
            self.roi,
        )

        self.edge = _number(
            self.edge,
        )

        self.spread = _number(
            self.spread,
        )

        self.expected_return = _number(
            self.expected_return,
        )

        self.breakeven = _number(
            self.breakeven,
        )

        self.confidence = _number(
            self.confidence,
        )

        if 0 <= self.confidence <= 1:
            self.confidence *= 100

        self.confidence = round(
            min(
                100.0,
                max(
                    0.0,
                    self.confidence,
                ),
            ),
            2,
        )

        self.match_score = _number(
            self.match_score,
        )

        self.risk = RiskResult.from_value(
            self.risk
        )

        self.stake = StakeResult.from_value(
            self.stake
        )

        self.score = _number(
            self.score,
        )

        self.approved = bool(
            self.approved
        )

        self.created_at = _datetime_value(
            self.created_at
        )

        self.volume_yes = max(
            0.0,
            _number(
                self.volume_yes,
            ),
        )

        self.volume_no = max(
            0.0,
            _number(
                self.volume_no,
            ),
        )

        self.liquidity_yes = max(
            0.0,
            _number(
                self.liquidity_yes,
            ),
        )

        self.liquidity_no = max(
            0.0,
            _number(
                self.liquidity_no,
            ),
        )

        if not self.platforms:
            self.platforms = [
                self.buy_yes_platform,
                self.buy_no_platform,
            ]

        if not isinstance(
            self.metadata,
            dict,
        ):
            self.metadata = dict(
                self.metadata
                or {}
            )

    @classmethod
    def from_dict(
        cls,
        data: Mapping[str, Any],
    ) -> Opportunity:
        """
        Converte um dicionário canônico
        ou legado em Opportunity.
        """

        if not isinstance(
            data,
            Mapping,
        ):
            raise TypeError(
                "Opportunity.from_dict exige "
                "um objeto Mapping."
            )

        prices = data.get(
            "prices",
            {},
        )

        if not isinstance(
            prices,
            Mapping,
        ):
            prices = {}

        stake = data.get(
            "stake",
            {},
        )

        if not isinstance(
            stake,
            Mapping,
        ):
            stake = {}

        yes_price = data.get(
            "yes_price",
            prices.get(
                "yes",
            ),
        )

        no_price = data.get(
            "no_price",
            prices.get(
                "no",
            ),
        )

        if yes_price is None:
            raise ValueError(
                "Campo obrigatório ausente: "
                "yes_price."
            )

        if no_price is None:
            raise ValueError(
                "Campo obrigatório ausente: "
                "no_price."
            )

        calculated_cost = (
            _number(yes_price)
            + _number(no_price)
        )

        cost = data.get(
            "cost",
            stake.get(
                "total",
                calculated_cost,
            ),
        )

        profit = data.get(
            "profit",
            1.0 - _number(cost),
        )

        roi = data.get(
            "roi",
            (
                _number(profit)
                / _number(cost)
                * 100
                if _number(cost) > 0
                else 0.0
            ),
        )

        similarity = _number(
            data.get(
                "similarity",
                0.0,
            )
        )

        confidence = data.get(
            "confidence",
            (
                similarity * 100
                if 0 <= similarity <= 1
                else similarity
            ),
        )

        return cls(
            question=data.get(
                "question",
                "",
            ),
            buy_yes_platform=data.get(
                "buy_yes_platform",
                "",
            ),
            buy_no_platform=data.get(
                "buy_no_platform",
                "",
            ),
            yes_price=yes_price,
            no_price=no_price,
            cost=cost,
            profit=profit,
            roi=roi,
            edge=data.get(
                "edge",
                profit,
            ),
            spread=data.get(
                "spread",
                profit,
            ),
            expected_return=data.get(
                "expected_return",
                profit,
            ),
            breakeven=data.get(
                "breakeven",
                cost,
            ),
            confidence=confidence,
            match_score=data.get(
                "match_score",
                confidence,
            ),
            risk=RiskResult.from_value(
                data.get(
                    "risk",
                )
            ),
            stake=StakeResult.from_value(
                stake
            ),
            score=data.get(
                "score",
                0.0,
            ),
            approved=data.get(
                "approved",
                False,
            ),
            created_at=data.get(
                "created_at",
            ),
            opportunity_id=data.get(
                "opportunity_id",
                "",
            ),
            market_id=data.get(
                "market_id",
                "",
            ),
            matched_question=data.get(
                "matched_question",
                "",
            ),
            platforms=list(
                data.get(
                    "platforms",
                    [],
                )
                or []
            ),
            connector_yes=data.get(
                "connector_yes",
                "",
            ),
            connector_no=data.get(
                "connector_no",
                "",
            ),
            volume_yes=data.get(
                "volume_yes",
                0.0,
            ),
            volume_no=data.get(
                "volume_no",
                0.0,
            ),
            liquidity_yes=data.get(
                "liquidity_yes",
                0.0,
            ),
            liquidity_no=data.get(
                "liquidity_no",
                0.0,
            ),
            liquidity=dict(
                data.get(
                    "liquidity",
                    {},
                )
                or {}
            ),
            slippage=dict(
                data.get(
                    "slippage",
                    {},
                )
                or {}
            ),
            portfolio=dict(
                data.get(
                    "portfolio",
                    {},
                )
                or {}
            ),
            market_yes=data.get(
                "market_yes",
            ),
            market_no=data.get(
                "market_no",
            ),
            orders=list(
                data.get(
                    "orders",
                    [],
                )
                or []
            ),
            adjusted_profit=data.get(
                "adjusted_profit",
            ),
            adjusted_roi=data.get(
                "adjusted_roi",
            ),
            metadata=dict(
                data.get(
                    "metadata",
                    {},
                )
                or {}
            ),
        )

    def to_dict(self) -> dict[str, Any]:
        """
        Converte o modelo para o formato
        utilizado pelas APIs e pelo Pipeline.
        """

        return {
            "opportunity_id": (
                self.opportunity_id
            ),
            "market_id": self.market_id,
            "question": self.question,
            "matched_question": (
                self.matched_question
            ),
            "buy_yes_platform": (
                self.buy_yes_platform
            ),
            "buy_no_platform": (
                self.buy_no_platform
            ),
            "platforms": list(
                self.platforms
            ),
            "connector_yes": (
                self.connector_yes
            ),
            "connector_no": (
                self.connector_no
            ),
            "yes_price": self.yes_price,
            "no_price": self.no_price,
            "cost": self.cost,
            "profit": self.profit,
            "roi": self.roi,
            "edge": self.edge,
            "spread": self.spread,
            "expected_return": (
                self.expected_return
            ),
            "breakeven": self.breakeven,
            "confidence": self.confidence,
            "match_score": self.match_score,
            "volume_yes": self.volume_yes,
            "volume_no": self.volume_no,
            "liquidity_yes": (
                self.liquidity_yes
            ),
            "liquidity_no": (
                self.liquidity_no
            ),
            "liquidity": dict(
                self.liquidity
            ),
            "risk": self.risk.to_dict(),
            "stake": self.stake.to_dict(),
            "slippage": dict(
                self.slippage
            ),
            "portfolio": dict(
                self.portfolio
            ),
            "score": self.score,
            "approved": self.approved,
            "created_at": (
                self.created_at.isoformat()
                if self.created_at
                else None
            ),
            "market_yes": self.market_yes,
            "market_no": self.market_no,
            "orders": list(
                self.orders
            ),
            "adjusted_profit": (
                self.adjusted_profit
            ),
            "adjusted_roi": (
                self.adjusted_roi
            ),
            "prices": {
                "yes": self.yes_price,
                "no": self.no_price,
            },
            "metadata": dict(
                self.metadata
            ),
        }

    def __getitem__(
        self,
        key: str,
    ) -> Any:
        """
        Suporte ao acesso legado:

            opportunity["profit"]
        """

        if key == "prices":
            return {
                "yes": self.yes_price,
                "no": self.no_price,
            }

        if hasattr(self, key):
            return getattr(
                self,
                key,
            )

        if key in self.metadata:
            return self.metadata[key]

        raise KeyError(key)

    def __setitem__(
        self,
        key: str,
        value: Any,
    ) -> None:
        """
        Suporte à atribuição legada.
        """

        if key == "prices":
            if not isinstance(
                value,
                Mapping,
            ):
                raise TypeError(
                    "prices deve ser "
                    "um objeto Mapping."
                )

            self.yes_price = _probability(
                value.get(
                    "yes",
                ),
                "yes_price",
            )

            self.no_price = _probability(
                value.get(
                    "no",
                ),
                "no_price",
            )

            return

        if key == "risk":
            self.risk = RiskResult.from_value(
                value
            )
            return

        if key == "stake":
            self.stake = StakeResult.from_value(
                value
            )
            return

        if key == "created_at":
            self.created_at = _datetime_value(
                value
            )
            return

        if hasattr(self, key):
            setattr(
                self,
                key,
                value,
            )

            return

        self.metadata[key] = value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        try:
            return self[key]

        except KeyError:
            return default

    def __contains__(
        self,
        key: object,
    ) -> bool:
        if not isinstance(key, str):
            return False

        return (
            key == "prices"
            or hasattr(self, key)
            or key in self.metadata
        )