from __future__ import annotations

from collections.abc import Mapping
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from math import isfinite
from typing import Any

from app.core.settings import settings
from app.paper.paper_account import PaperAccount, paper_account


def _number(value: Any, default: float = 0.0) -> float:
    if value is None or isinstance(value, bool):
        return float(default)
    try:
        resolved = float(value)
    except (TypeError, ValueError):
        return float(default)
    return resolved if isfinite(resolved) else float(default)


def _read(target: Any, name: str, default: Any = None) -> Any:
    if isinstance(target, Mapping):
        return target.get(name, default)
    if target is None:
        return default
    return getattr(target, name, default)


def _normalized_ratio(value: Any, default: float = 0.0) -> float:
    resolved = _number(value, default)
    if resolved > 1.0 and resolved <= 100.0:
        resolved /= 100.0
    return min(1.0, max(0.0, resolved))


def _utc_date(value: Any) -> str | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    try:
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc).date().isoformat()


@dataclass(frozen=True, slots=True)
class PaperRiskLimits:
    """Limites exclusivos da conta Paper. Nenhum campo habilita execução live."""

    enabled: bool = True
    max_trade_notional: float = 500.0
    max_total_exposure: float = 2_500.0
    max_market_exposure: float = 1_000.0
    max_open_positions: int = 10
    max_daily_trades: int = 20
    daily_loss_limit: float = 500.0
    max_drawdown_rate: float = 0.10
    min_roi: float = 0.0
    min_confidence: float = 0.0
    max_risk_score: float = 100.0

    def __post_init__(self) -> None:
        positive_names = (
            "max_trade_notional",
            "max_total_exposure",
            "max_market_exposure",
            "daily_loss_limit",
        )
        for name in positive_names:
            value = _number(getattr(self, name), -1.0)
            if value <= 0:
                raise ValueError(f"{name} deve ser maior que zero.")
            object.__setattr__(self, name, value)

        if int(self.max_open_positions) <= 0:
            raise ValueError("max_open_positions deve ser maior que zero.")
        if int(self.max_daily_trades) <= 0:
            raise ValueError("max_daily_trades deve ser maior que zero.")
        object.__setattr__(self, "max_open_positions", int(self.max_open_positions))
        object.__setattr__(self, "max_daily_trades", int(self.max_daily_trades))

        drawdown = _normalized_ratio(self.max_drawdown_rate, -1.0)
        if not 0 < drawdown <= 1:
            raise ValueError("max_drawdown_rate deve estar entre 0 e 1.")
        object.__setattr__(self, "max_drawdown_rate", drawdown)

        confidence = _normalized_ratio(self.min_confidence, 0.0)
        object.__setattr__(self, "min_confidence", confidence)

        max_risk = _number(self.max_risk_score, 100.0)
        if not 0 <= max_risk <= 100:
            raise ValueError("max_risk_score deve estar entre 0 e 100.")
        object.__setattr__(self, "max_risk_score", max_risk)
        object.__setattr__(self, "min_roi", _number(self.min_roi, 0.0))

    @classmethod
    def from_settings(cls) -> "PaperRiskLimits":
        return cls(
            enabled=settings.PAPER_RISK_ENABLED,
            max_trade_notional=settings.PAPER_RISK_MAX_TRADE_NOTIONAL,
            max_total_exposure=settings.PAPER_RISK_MAX_TOTAL_EXPOSURE,
            max_market_exposure=settings.PAPER_RISK_MAX_MARKET_EXPOSURE,
            max_open_positions=settings.PAPER_RISK_MAX_OPEN_POSITIONS,
            max_daily_trades=settings.PAPER_RISK_MAX_DAILY_TRADES,
            daily_loss_limit=settings.PAPER_RISK_DAILY_LOSS_LIMIT,
            max_drawdown_rate=settings.PAPER_RISK_MAX_DRAWDOWN_RATE,
            min_roi=settings.PAPER_RISK_MIN_ROI,
            min_confidence=settings.PAPER_RISK_MIN_CONFIDENCE,
            max_risk_score=settings.PAPER_RISK_MAX_RISK_SCORE,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class PaperRiskDecision:
    approved: bool
    codes: list[str] = field(default_factory=list)
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)
    limits: dict[str, Any] = field(default_factory=dict)

    @property
    def stopped(self) -> bool:
        return any(
            code in {"DAILY_LOSS_LIMIT", "MAX_DRAWDOWN", "DAILY_TRADE_LIMIT"}
            for code in self.codes
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "approved": bool(self.approved),
            "stopped": self.stopped,
            "codes": list(self.codes),
            "reasons": list(self.reasons),
            "metrics": dict(self.metrics),
            "limits": dict(self.limits),
            "mode": "PAPER",
            "execution_authorized": False,
            "live_execution": False,
        }


class PaperRiskGuard:
    """Avalia exposição, perda diária e qualidade antes do PaperStage."""

    def __init__(
        self,
        *,
        account: PaperAccount | None = None,
        limits: PaperRiskLimits | None = None,
    ) -> None:
        self.account = account or paper_account
        self.limits = limits or PaperRiskLimits.from_settings()
        self.last_decision: PaperRiskDecision | None = None

    @staticmethod
    def _stake_total(opportunity: Any) -> float:
        stake = _read(opportunity, "stake", {})
        total = _read(stake, "total", None)
        if total is None:
            total = _number(_read(stake, "yes", 0.0)) + _number(
                _read(stake, "no", 0.0)
            )
        return max(0.0, _number(total, 0.0))

    @staticmethod
    def _market_name(opportunity: Any) -> str:
        return str(
            _read(opportunity, "question", None)
            or _read(opportunity, "market_id", None)
            or "unknown"
        ).strip()

    @staticmethod
    def _risk_score(opportunity: Any) -> float:
        nested = _read(opportunity, "risk", None)
        return _number(
            _read(nested, "score", _read(opportunity, "risk_score", 0.0)),
            0.0,
        )

    @staticmethod
    def _position_exposure(position: Mapping[str, Any]) -> float:
        return max(
            0.0,
            _number(position.get("cost_basis"), 0.0),
            _number(position.get("market_value"), 0.0),
        )

    def _account_metrics(self) -> dict[str, Any]:
        snapshot = self.account.snapshot(include_trades=True)
        open_positions = [
            item
            for item in snapshot.get("positions", [])
            if str(item.get("status", "")).upper() == "OPEN"
            and _number(item.get("quantity"), 0.0) > 0
        ]
        total_exposure = sum(self._position_exposure(item) for item in open_positions)
        exposure_by_market: dict[str, float] = {}
        for item in open_positions:
            market = str(item.get("market") or item.get("symbol") or "unknown").strip()
            exposure_by_market[market] = exposure_by_market.get(market, 0.0) + self._position_exposure(item)

        today = datetime.now(timezone.utc).date().isoformat()
        trades_today = [
            item
            for item in snapshot.get("trades", [])
            if _utc_date(item.get("executed_at")) == today
        ]
        points_today = [
            item
            for item in snapshot.get("equity_curve", [])
            if _utc_date(item.get("timestamp")) == today
        ]
        current_equity = _number(snapshot.get("equity"), 0.0)
        start_equity = (
            _number(points_today[0].get("equity"), current_equity)
            if points_today
            else current_equity
        )
        daily_pnl = current_equity - start_equity
        analytics = snapshot.get("equity_analytics") or {}
        wallet = snapshot.get("wallet") or {}
        return {
            "snapshot": snapshot,
            "open_positions": len(open_positions),
            "total_exposure": round(total_exposure, 8),
            "exposure_by_market": {
                key: round(value, 8) for key, value in exposure_by_market.items()
            },
            "daily_trades": len(trades_today),
            "daily_start_equity": round(start_equity, 8),
            "current_equity": round(current_equity, 8),
            "daily_pnl": round(daily_pnl, 8),
            "daily_loss": round(max(0.0, -daily_pnl), 8),
            "max_drawdown_rate": _number(analytics.get("max_drawdown_rate"), 0.0),
            "available_cash": _number(wallet.get("available"), 0.0),
        }

    def session_status(self) -> PaperRiskDecision:
        metrics = self._account_metrics()
        codes: list[str] = []
        reasons: list[str] = []
        limits = self.limits

        if metrics["daily_loss"] >= limits.daily_loss_limit:
            codes.append("DAILY_LOSS_LIMIT")
            reasons.append("O limite de perda diária da conta Paper foi atingido.")
        if metrics["max_drawdown_rate"] >= limits.max_drawdown_rate:
            codes.append("MAX_DRAWDOWN")
            reasons.append("O drawdown máximo permitido da conta Paper foi atingido.")
        if metrics["daily_trades"] >= limits.max_daily_trades:
            codes.append("DAILY_TRADE_LIMIT")
            reasons.append("O limite diário de trades Paper foi atingido.")

        decision = PaperRiskDecision(
            approved=not codes,
            codes=codes,
            reasons=reasons,
            metrics={key: value for key, value in metrics.items() if key != "snapshot"},
            limits=limits.to_dict(),
        )
        self.last_decision = decision
        return decision

    def evaluate(self, opportunity: Any) -> PaperRiskDecision:
        if not self.limits.enabled:
            decision = PaperRiskDecision(
                approved=True,
                codes=[],
                reasons=[],
                metrics={"risk_enabled": False},
                limits=self.limits.to_dict(),
            )
            self.last_decision = decision
            return decision

        session = self.session_status()
        codes = list(session.codes)
        reasons = list(session.reasons)
        metrics = dict(session.metrics)

        stake_total = self._stake_total(opportunity)
        market = self._market_name(opportunity)
        roi = _number(_read(opportunity, "roi", 0.0), 0.0)
        confidence = _normalized_ratio(_read(opportunity, "confidence", 0.0), 0.0)
        risk_score = self._risk_score(opportunity)
        existing_market_exposure = _number(
            metrics.get("exposure_by_market", {}).get(market), 0.0
        )
        projected_total = _number(metrics.get("total_exposure"), 0.0) + stake_total
        projected_market = existing_market_exposure + stake_total
        projected_positions = int(metrics.get("open_positions", 0)) + 2
        projected_daily_trades = int(metrics.get("daily_trades", 0)) + 2

        if stake_total <= 0:
            codes.append("INVALID_STAKE")
            reasons.append("A oportunidade não possui stake Paper válida.")
        if stake_total > self.limits.max_trade_notional + 1e-9:
            codes.append("TRADE_NOTIONAL_LIMIT")
            reasons.append("A stake excede o limite por oportunidade Paper.")
        if projected_total > self.limits.max_total_exposure + 1e-9:
            codes.append("TOTAL_EXPOSURE_LIMIT")
            reasons.append("A exposição total projetada excede o limite Paper.")
        if projected_market > self.limits.max_market_exposure + 1e-9:
            codes.append("MARKET_EXPOSURE_LIMIT")
            reasons.append("A exposição projetada no mercado excede o limite Paper.")
        if projected_positions > self.limits.max_open_positions:
            codes.append("OPEN_POSITIONS_LIMIT")
            reasons.append("O número projetado de posições abertas excede o limite Paper.")
        if projected_daily_trades > self.limits.max_daily_trades:
            codes.append("DAILY_TRADE_LIMIT")
            reasons.append("A operação excederia o limite diário de trades Paper.")
        if stake_total > _number(metrics.get("available_cash"), 0.0) + 1e-9:
            codes.append("INSUFFICIENT_CASH")
            reasons.append("A conta Paper não possui caixa disponível para a stake.")
        if roi < self.limits.min_roi:
            codes.append("ROI_BELOW_MINIMUM")
            reasons.append("O ROI está abaixo do mínimo configurado para a sessão Paper.")
        if confidence < self.limits.min_confidence:
            codes.append("CONFIDENCE_BELOW_MINIMUM")
            reasons.append("A confiança está abaixo do mínimo configurado para a sessão Paper.")
        if risk_score > self.limits.max_risk_score:
            codes.append("RISK_SCORE_ABOVE_MAXIMUM")
            reasons.append("O score de risco excede o máximo configurado para a sessão Paper.")

        metrics.update(
            {
                "stake_total": round(stake_total, 8),
                "market": market,
                "roi": round(roi, 8),
                "confidence": round(confidence, 8),
                "risk_score": round(risk_score, 8),
                "projected_total_exposure": round(projected_total, 8),
                "projected_market_exposure": round(projected_market, 8),
                "projected_open_positions": projected_positions,
                "projected_daily_trades": projected_daily_trades,
            }
        )
        # Remove repetições preservando a ordem.
        unique_codes = list(dict.fromkeys(codes))
        unique_reasons = list(dict.fromkeys(reasons))
        decision = PaperRiskDecision(
            approved=not unique_codes,
            codes=unique_codes,
            reasons=unique_reasons,
            metrics=metrics,
            limits=self.limits.to_dict(),
        )
        self.last_decision = decision
        return decision

    def status(self) -> dict[str, Any]:
        current = self.session_status()
        return {
            "status": "READY" if current.approved else "STOPPED",
            "enabled": self.limits.enabled,
            "limits": self.limits.to_dict(),
            "session": current.to_dict(),
            "execution_authorized": False,
            "live_execution": False,
        }


paper_risk_guard = PaperRiskGuard()
