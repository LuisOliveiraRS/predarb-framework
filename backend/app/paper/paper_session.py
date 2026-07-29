from __future__ import annotations

import json
import os
from collections import deque
from collections.abc import Callable, Iterable, Mapping
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any
from uuid import uuid4

from app.core.settings import settings
from app.paper.paper_account import PaperAccount, paper_account
from app.paper.paper_risk import PaperRiskGuard, paper_risk_guard
from app.pipeline.pipeline_builder import PipelineBuilder


def _utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (str, bytes, Mapping)):
        return [value]
    if isinstance(value, Iterable):
        return list(value)
    return [value]


class PaperSessionRepository:
    """Persistência JSON atômica do relatório da sessão Paper."""

    def __init__(self, path: str | Path) -> None:
        self.path = Path(path)
        if self.path.suffix.lower() != ".json":
            raise ValueError("O relatório da sessão Paper deve usar um arquivo .json.")

    def save(self, payload: Mapping[str, Any]) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        data = json.dumps(dict(payload), ensure_ascii=False, indent=2, sort_keys=True)
        temporary.write_text(data, encoding="utf-8")
        os.replace(temporary, self.path)
        return self.path

    def load(self) -> dict[str, Any] | None:
        if not self.path.is_file():
            return None
        payload = json.loads(self.path.read_text(encoding="utf-8"))
        if not isinstance(payload, dict):
            raise ValueError("Relatório inválido da sessão Paper.")
        return payload

    def status(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "exists": self.path.is_file(),
            "execution_authorized": False,
        }


class PaperSessionManager:
    """Executa ciclos Paper sobre sinais reais ou fornecidos explicitamente."""

    def __init__(
        self,
        *,
        account: PaperAccount | None = None,
        risk_guard: PaperRiskGuard | None = None,
        opportunity_source: Callable[[], Any] | None = None,
        repository: PaperSessionRepository | None = None,
        stake_amount: float | None = None,
        max_opportunities_per_cycle: int | None = None,
        paper_fee_rate: float | None = None,
        history_size: int = 500,
    ) -> None:
        self._lock = RLock()
        self.account = account or paper_account
        self.risk_guard = risk_guard or paper_risk_guard
        self.opportunity_source = opportunity_source
        self.repository = repository or PaperSessionRepository(
            settings.PAPER_SESSION_REPORT_PATH
        )
        self.stake_amount = float(
            settings.PAPER_SESSION_STAKE_AMOUNT
            if stake_amount is None
            else stake_amount
        )
        self.max_opportunities_per_cycle = int(
            settings.PAPER_SESSION_MAX_OPPORTUNITIES_PER_CYCLE
            if max_opportunities_per_cycle is None
            else max_opportunities_per_cycle
        )
        self.paper_fee_rate = float(
            settings.PAPER_SESSION_FEE_RATE
            if paper_fee_rate is None
            else paper_fee_rate
        )
        if self.stake_amount <= 0:
            raise ValueError("stake_amount deve ser positivo.")
        if self.max_opportunities_per_cycle <= 0:
            raise ValueError("max_opportunities_per_cycle deve ser positivo.")
        if self.paper_fee_rate < 0:
            raise ValueError("paper_fee_rate não pode ser negativo.")
        self._cycles: deque[dict[str, Any]] = deque(maxlen=max(10, int(history_size)))
        self.session_id = str(uuid4())
        self.created_at = _utc_iso()
        self.updated_at = self.created_at
        self.last_cycle: dict[str, Any] | None = None
        self.total_cycles = 0
        self.successful_cycles = 0
        self.failed_cycles = 0
        self.no_signal_cycles = 0
        self.risk_stopped_cycles = 0
        self.last_error: str | None = None

    @staticmethod
    def _default_source() -> list[Any]:
        from app.engine.arbitrage_engine import arbitrage_engine

        return _as_list(arbitrage_engine.scan(publish=False))

    def _source(self) -> list[Any]:
        source = self.opportunity_source or self._default_source
        return _as_list(source())

    def _pipeline(self):
        snapshot = self.account.snapshot(include_trades=False)
        bankroll = max(1.0, float(snapshot.get("equity", self.stake_amount) or 1.0))
        return PipelineBuilder().build_paper(
            name="paper-session",
            stop_on_error=True,
            strict_validation=False,
            require_liquidity=False,
            bankroll_per_opportunity=self.stake_amount,
            total_bankroll=bankroll,
            max_position_size=1.0,
            max_total_exposure=1.0,
            ranking_limit=self.max_opportunities_per_cycle,
            paper_fee_rate=self.paper_fee_rate,
            persist_paper_account=True,
            paper_account=self.account,
            paper_account_persist=True,
            paper_risk_enabled=True,
            paper_risk_guard=self.risk_guard,
        )

    def _record(self, cycle: dict[str, Any]) -> dict[str, Any]:
        with self._lock:
            self._cycles.append(deepcopy(cycle))
            self.last_cycle = deepcopy(cycle)
            self.total_cycles += 1
            status = cycle.get("status")
            if status == "SUCCESS":
                self.successful_cycles += 1
            elif status == "NO_SIGNAL":
                self.no_signal_cycles += 1
            elif status == "RISK_STOPPED":
                self.risk_stopped_cycles += 1
            else:
                self.failed_cycles += 1
            self.last_error = cycle.get("error")
            self.updated_at = cycle["finished_at"]
            self.repository.save(self.report())
        return deepcopy(cycle)

    def run_cycle(self, opportunities: Any = None) -> dict[str, Any]:
        cycle_id = str(uuid4())
        started_at = _utc_iso()
        session_risk = self.risk_guard.session_status()
        if not session_risk.approved:
            return self._record(
                {
                    "cycle_id": cycle_id,
                    "status": "RISK_STOPPED",
                    "started_at": started_at,
                    "finished_at": _utc_iso(),
                    "input_opportunities": 0,
                    "orders": 0,
                    "fills": 0,
                    "risk": session_risk.to_dict(),
                    "account": self.account.snapshot(include_trades=False),
                    "execution_authorized": False,
                    "live_execution": False,
                }
            )

        try:
            resolved = self._source() if opportunities is None else _as_list(opportunities)
            if not resolved:
                return self._record(
                    {
                        "cycle_id": cycle_id,
                        "status": "NO_SIGNAL",
                        "started_at": started_at,
                        "finished_at": _utc_iso(),
                        "input_opportunities": 0,
                        "orders": 0,
                        "fills": 0,
                        "risk": session_risk.to_dict(),
                        "account": self.account.snapshot(include_trades=False),
                        "execution_authorized": False,
                        "live_execution": False,
                    }
                )

            result = self._pipeline().execute(resolved)
            context = result.context
            risk_metadata = dict(context.metadata.get("paper_risk") or {})
            account_metadata = dict(context.metadata.get("paper_account") or {})
            orders = list(context.orders or [])
            reports = list(context.execution_reports or [])
            filled = [
                item
                for item in reports
                if str((item or {}).get("status", "")).upper() == "FILLED"
            ]
            status = "SUCCESS" if result.success and filled else "RISK_REJECTED"
            if result.errors:
                status = "FAILED"

            return self._record(
                {
                    "cycle_id": cycle_id,
                    "status": status,
                    "started_at": started_at,
                    "finished_at": _utc_iso(),
                    "input_opportunities": len(resolved),
                    "approved_opportunities": int(risk_metadata.get("approved", 0)),
                    "rejected_opportunities": int(risk_metadata.get("rejected", 0)),
                    "orders": len(orders),
                    "fills": len(filled),
                    "errors": list(result.errors),
                    "risk": risk_metadata,
                    "paper_account": account_metadata,
                    "account": self.account.snapshot(include_trades=False),
                    "execution_authorized": False,
                    "live_execution": False,
                }
            )
        except Exception as exc:
            return self._record(
                {
                    "cycle_id": cycle_id,
                    "status": "FAILED",
                    "started_at": started_at,
                    "finished_at": _utc_iso(),
                    "input_opportunities": 0,
                    "orders": 0,
                    "fills": 0,
                    "error": str(exc),
                    "account": self.account.snapshot(include_trades=False),
                    "execution_authorized": False,
                    "live_execution": False,
                }
            )

    def restore_report(self) -> bool:
        payload = self.repository.load()
        if payload is None:
            return False
        cycles = payload.get("cycles", [])
        if not isinstance(cycles, list):
            raise ValueError("Relatório da sessão Paper contém cycles inválido.")
        with self._lock:
            self._cycles.clear()
            for item in cycles[-self._cycles.maxlen :]:
                if isinstance(item, Mapping):
                    self._cycles.append(deepcopy(dict(item)))
            self.session_id = str(payload.get("session_id") or self.session_id)
            self.created_at = str(payload.get("created_at") or self.created_at)
            self.updated_at = str(payload.get("updated_at") or self.created_at)
            self.total_cycles = max(0, int(payload.get("total_cycles", len(self._cycles))))
            self.successful_cycles = max(0, int(payload.get("successful_cycles", 0)))
            self.failed_cycles = max(0, int(payload.get("failed_cycles", 0)))
            self.no_signal_cycles = max(0, int(payload.get("no_signal_cycles", 0)))
            self.risk_stopped_cycles = max(0, int(payload.get("risk_stopped_cycles", 0)))
            last_cycle = payload.get("last_cycle")
            self.last_cycle = deepcopy(last_cycle) if isinstance(last_cycle, Mapping) else None
            self.last_error = payload.get("last_error") or None
        return True

    def report(self) -> dict[str, Any]:
        with self._lock:
            account = self.account.snapshot(include_trades=False)
            return {
                "status": "READY",
                "mode": "PAPER",
                "session_id": self.session_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "total_cycles": self.total_cycles,
                "successful_cycles": self.successful_cycles,
                "failed_cycles": self.failed_cycles,
                "no_signal_cycles": self.no_signal_cycles,
                "risk_stopped_cycles": self.risk_stopped_cycles,
                "last_error": self.last_error,
                "last_cycle": deepcopy(self.last_cycle),
                "cycles": deepcopy(list(self._cycles)),
                "risk": self.risk_guard.status(),
                "account": account,
                "repository": self.repository.status(),
                "execution_authorized": False,
                "live_execution": False,
            }

    def reset_report(self) -> dict[str, Any]:
        with self._lock:
            self._cycles.clear()
            self.session_id = str(uuid4())
            self.created_at = _utc_iso()
            self.updated_at = self.created_at
            self.last_cycle = None
            self.total_cycles = 0
            self.successful_cycles = 0
            self.failed_cycles = 0
            self.no_signal_cycles = 0
            self.risk_stopped_cycles = 0
            self.last_error = None
            self.repository.save(self.report())
            return self.report()


paper_session_manager = PaperSessionManager()
