from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

from app.paper.performance import (
    PaperPerformanceService,
)


def _number(
    value: Any,
    default: float = 0.0,
) -> float:
    if value is None or isinstance(value, bool):
        return float(default)

    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _integer(
    value: Any,
    default: int = 0,
) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return int(default)


def _env_float(
    name: str,
    default: float,
) -> float:
    value = os.getenv(name)

    if value is None:
        return float(default)

    try:
        return float(value)
    except ValueError:
        return float(default)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(
    value: Any,
) -> datetime | None:
    if not value:
        return None

    normalized = str(value).strip()

    if normalized.endswith("Z"):
        normalized = (
            normalized[:-1]
            + "+00:00"
        )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError:
        return None

    if parsed.tzinfo is None:
        parsed = parsed.replace(
            tzinfo=timezone.utc
        )

    return parsed.astimezone(
        timezone.utc
    )


@dataclass(frozen=True)
class MonitorThresholds:
    max_failed_cycle_rate: float
    min_success_cycle_rate: float
    max_drawdown_rate: float
    stale_hours: float

    @classmethod
    def from_env(
        cls,
    ) -> "MonitorThresholds":
        return cls(
            max_failed_cycle_rate=max(
                0.0,
                min(
                    1.0,
                    _env_float(
                        "PAPER_MONITOR_MAX_FAILED_CYCLE_RATE",
                        0.20,
                    ),
                ),
            ),
            min_success_cycle_rate=max(
                0.0,
                min(
                    1.0,
                    _env_float(
                        "PAPER_MONITOR_MIN_SUCCESS_CYCLE_RATE",
                        0.60,
                    ),
                ),
            ),
            max_drawdown_rate=max(
                0.0,
                min(
                    1.0,
                    _env_float(
                        "PAPER_MONITOR_MAX_DRAWDOWN_RATE",
                        0.05,
                    ),
                ),
            ),
            stale_hours=max(
                1.0,
                _env_float(
                    "PAPER_MONITOR_STALE_HOURS",
                    24.0,
                ),
            ),
        )


@dataclass(frozen=True)
class PerformanceAlert:
    code: str
    severity: str
    title: str
    message: str
    current_value: float | int | str | None = None
    threshold: float | int | str | None = None

    def to_dict(
        self,
    ) -> dict[str, Any]:
        return asdict(self)


class PaperPerformanceMonitor:
    """Diagnóstico somente leitura do desempenho Paper."""

    def __init__(
        self,
        service: PaperPerformanceService | None = None,
        thresholds: MonitorThresholds | None = None,
        now: datetime | None = None,
    ) -> None:
        self.service = (
            service
            if service is not None
            else PaperPerformanceService()
        )

        self.thresholds = (
            thresholds
            if thresholds is not None
            else MonitorThresholds.from_env()
        )

        resolved_now = (
            now
            if now is not None
            else _utc_now()
        )

        if resolved_now.tzinfo is None:
            resolved_now = resolved_now.replace(
                tzinfo=timezone.utc
            )

        self.now = resolved_now.astimezone(
            timezone.utc
        )

    @staticmethod
    def _rates(
        summary: Mapping[str, Any],
    ) -> dict[str, float]:
        cycles = _integer(
            summary.get("total_cycles")
        )

        successful = _integer(
            summary.get("successful_cycles")
        )

        failed = _integer(
            summary.get("failed_cycles")
        )

        no_signal = _integer(
            summary.get("no_signal_cycles")
        )

        if cycles <= 0:
            return {
                "success_cycle_rate": 0.0,
                "failed_cycle_rate": 0.0,
                "no_signal_cycle_rate": 0.0,
            }

        return {
            "success_cycle_rate": round(
                successful / cycles,
                8,
            ),
            "failed_cycle_rate": round(
                failed / cycles,
                8,
            ),
            "no_signal_cycle_rate": round(
                no_signal / cycles,
                8,
            ),
        }

    def _staleness_hours(
        self,
        summary: Mapping[str, Any],
    ) -> float | None:
        finished_at = _parse_datetime(
            summary.get(
                "latest_finished_at"
            )
        )

        if finished_at is None:
            return None

        elapsed = (
            self.now - finished_at
        ).total_seconds() / 3600

        return round(
            max(0.0, elapsed),
            4,
        )

    def _build_alerts(
        self,
        summary: Mapping[str, Any],
        rates: Mapping[str, float],
        staleness_hours: float | None,
    ) -> list[PerformanceAlert]:
        alerts: list[PerformanceAlert] = []

        total_reports = _integer(
            summary.get("total_reports")
        )

        total_cycles = _integer(
            summary.get("total_cycles")
        )

        total_trades = _integer(
            summary.get("total_trades")
        )

        endpoint_errors = _integer(
            summary.get("endpoint_errors")
        )

        safety_violations = _integer(
            summary.get("safety_violations")
        )

        drawdown_rate = _number(
            summary.get("max_drawdown_rate")
        )

        failed_cycle_rate = _number(
            rates.get("failed_cycle_rate")
        )

        success_cycle_rate = _number(
            rates.get("success_cycle_rate")
        )

        if safety_violations > 0:
            alerts.append(
                PerformanceAlert(
                    code="SAFETY_VIOLATION",
                    severity="critical",
                    title="Violação de segurança detectada",
                    message=(
                        "Os relatórios registraram uma "
                        "ou mais violações de segurança."
                    ),
                    current_value=safety_violations,
                    threshold=0,
                )
            )

        if endpoint_errors > 0:
            alerts.append(
                PerformanceAlert(
                    code="ENDPOINT_ERRORS",
                    severity="critical",
                    title="Erros de endpoint",
                    message=(
                        "Foram registrados erros durante "
                        "a coleta de dados da sessão."
                    ),
                    current_value=endpoint_errors,
                    threshold=0,
                )
            )

        if (
            total_cycles > 0
            and failed_cycle_rate
            > self.thresholds.max_failed_cycle_rate
        ):
            alerts.append(
                PerformanceAlert(
                    code="FAILED_CYCLE_RATE_HIGH",
                    severity="warning",
                    title="Taxa de falha elevada",
                    message=(
                        "A proporção de ciclos com falha "
                        "superou o limite configurado."
                    ),
                    current_value=failed_cycle_rate,
                    threshold=(
                        self.thresholds
                        .max_failed_cycle_rate
                    ),
                )
            )

        if (
            total_cycles > 0
            and success_cycle_rate
            < self.thresholds.min_success_cycle_rate
        ):
            alerts.append(
                PerformanceAlert(
                    code="SUCCESS_CYCLE_RATE_LOW",
                    severity="warning",
                    title="Taxa de sucesso abaixo do esperado",
                    message=(
                        "A proporção de ciclos concluídos "
                        "com sucesso ficou abaixo do mínimo."
                    ),
                    current_value=success_cycle_rate,
                    threshold=(
                        self.thresholds
                        .min_success_cycle_rate
                    ),
                )
            )

        if (
            drawdown_rate
            > self.thresholds.max_drawdown_rate
        ):
            alerts.append(
                PerformanceAlert(
                    code="DRAWDOWN_HIGH",
                    severity="warning",
                    title="Drawdown elevado",
                    message=(
                        "O drawdown máximo superou o "
                        "limite operacional configurado."
                    ),
                    current_value=drawdown_rate,
                    threshold=(
                        self.thresholds
                        .max_drawdown_rate
                    ),
                )
            )

        if (
            staleness_hours is not None
            and staleness_hours
            > self.thresholds.stale_hours
        ):
            alerts.append(
                PerformanceAlert(
                    code="DATA_STALE",
                    severity="warning",
                    title="Dados desatualizados",
                    message=(
                        "O relatório mais recente está "
                        "mais antigo que o limite definido."
                    ),
                    current_value=staleness_hours,
                    threshold=(
                        self.thresholds.stale_hours
                    ),
                )
            )

        if total_reports == 0:
            alerts.append(
                PerformanceAlert(
                    code="NO_REPORTS",
                    severity="info",
                    title="Nenhum relatório disponível",
                    message=(
                        "Execute uma sessão Paper para "
                        "iniciar o histórico operacional."
                    ),
                    current_value=0,
                    threshold=1,
                )
            )

        elif total_cycles == 0:
            alerts.append(
                PerformanceAlert(
                    code="NO_CYCLES",
                    severity="info",
                    title="Nenhum ciclo processado",
                    message=(
                        "Os relatórios existem, mas não "
                        "registraram ciclos processados."
                    ),
                    current_value=0,
                    threshold=1,
                )
            )

        elif total_trades == 0:
            alerts.append(
                PerformanceAlert(
                    code="NO_TRADES",
                    severity="info",
                    title="Nenhum trade Paper registrado",
                    message=(
                        "A sessão processou ciclos, mas "
                        "ainda não executou trades simulados."
                    ),
                    current_value=0,
                    threshold=1,
                )
            )

        return alerts

    @staticmethod
    def _score(
        summary: Mapping[str, Any],
        rates: Mapping[str, float],
        alerts: list[PerformanceAlert],
    ) -> int:
        score = 100

        total_reports = _integer(
            summary.get("total_reports")
        )

        if total_reports == 0:
            score -= 50

        severity_penalties = {
            "critical": 30,
            "warning": 12,
            "info": 4,
        }

        for alert in alerts:
            score -= severity_penalties.get(
                alert.severity,
                0,
            )

        success_rate = _number(
            rates.get("success_cycle_rate")
        )

        if success_rate >= 0.90:
            score += 5
        elif (
            total_reports > 0
            and success_rate < 0.50
        ):
            score -= 8

        # Um alerta crítico nunca pode resultar em score
        # de faixa saudável. O bônus de sucesso não pode
        # neutralizar uma violação de segurança ou erro
        # crítico de coleta.
        if any(
            alert.severity == "critical"
            for alert in alerts
        ):
            score = min(score, 74)

        return max(
            0,
            min(100, int(score)),
        )

    @staticmethod
    def _status(
        *,
        score: int,
        alerts: list[PerformanceAlert],
        total_reports: int,
    ) -> str:
        if total_reports == 0:
            return "NO_DATA"

        severities = {
            alert.severity
            for alert in alerts
        }

        if "critical" in severities:
            return "CRITICAL"

        if (
            "warning" in severities
            or score < 75
        ):
            return "WARNING"

        return "HEALTHY"

    def snapshot(
        self,
    ) -> dict[str, Any]:
        summary = self.service.summary()
        rates = self._rates(summary)
        staleness_hours = (
            self._staleness_hours(
                summary
            )
        )

        alerts = self._build_alerts(
            summary,
            rates,
            staleness_hours,
        )

        score = self._score(
            summary,
            rates,
            alerts,
        )

        total_reports = _integer(
            summary.get("total_reports")
        )

        return {
            "status": self._status(
                score=score,
                alerts=alerts,
                total_reports=total_reports,
            ),
            "score": score,
            "generated_at": (
                self.now.isoformat()
            ),
            "rates": rates,
            "staleness_hours": (
                staleness_hours
            ),
            "thresholds": asdict(
                self.thresholds
            ),
            "summary": summary,
            "alerts": [
                alert.to_dict()
                for alert in alerts
            ],
            "alert_counts": {
                "critical": sum(
                    1
                    for alert in alerts
                    if alert.severity
                    == "critical"
                ),
                "warning": sum(
                    1
                    for alert in alerts
                    if alert.severity
                    == "warning"
                ),
                "info": sum(
                    1
                    for alert in alerts
                    if alert.severity
                    == "info"
                ),
            },
            "execution_authorized": False,
            "live_execution": False,
            "read_only": True,
        }
