from __future__ import annotations

from pathlib import Path
from threading import RLock
from typing import Any

from app.core.settings import settings
from app.paper.paper_account import PaperAccount, paper_account
from app.paper.paper_position_manager import paper_position_manager
from app.paper.paper_repository import PaperAccountRepository
from app.paper.paper_trade_history import paper_trade_history
from app.paper.paper_wallet import paper_wallet


class PaperAccountRuntime:
    def __init__(
        self,
        *,
        enabled: bool | None = None,
        auto_load: bool | None = None,
        auto_save: bool | None = None,
        initial_balance: float | None = None,
        path: str | Path | None = None,
        account: PaperAccount | None = None,
    ) -> None:
        self._lock = RLock()
        self.enabled = settings.PAPER_ACCOUNT_ENABLED if enabled is None else bool(enabled)
        self.auto_load = (
            settings.PAPER_ACCOUNT_AUTO_LOAD if auto_load is None else bool(auto_load)
        )
        self.auto_save = (
            settings.PAPER_ACCOUNT_AUTO_SAVE if auto_save is None else bool(auto_save)
        )
        self.initial_balance = float(
            settings.PAPER_INITIAL_BALANCE
            if initial_balance is None
            else initial_balance
        )
        self.repository = PaperAccountRepository(
            settings.PAPER_ACCOUNT_PATH if path is None else path
        )
        self.account = account or paper_account
        self.account.repository = self.repository
        self.account.auto_persist = False
        self.started = False
        self.loaded = False
        self.last_report: dict[str, Any] = {}

    def startup(self) -> dict[str, Any]:
        with self._lock:
            if self.started:
                return self.status()
            loaded = False
            if self.enabled and self.auto_load and self.repository.exists():
                loaded = self.account.load()
            elif self.enabled:
                self.account.reset(initial_balance=self.initial_balance, persist=False)
            self.started = bool(self.enabled)
            self.loaded = bool(loaded)
            self.last_report = {
                "operation": "STARTUP",
                "status": "READY" if self.enabled else "DISABLED",
                "loaded": self.loaded,
                "file_exists": self.repository.exists(),
                "execution_authorized": False,
                "live_execution": False,
            }
            return self.status()

    def shutdown(self) -> dict[str, Any]:
        with self._lock:
            saved = False
            if (
                self.enabled
                and self.started
                and self.auto_save
                and self.account.snapshot(include_trades=False).get("dirty")
            ):
                self.account.save()
                saved = True
            self.started = False
            self.last_report = {
                "operation": "SHUTDOWN",
                "status": "STOPPED",
                "saved": saved,
                "execution_authorized": False,
                "live_execution": False,
            }
            return self.status()

    def status(self) -> dict[str, Any]:
        return {
            "status": (
                "READY"
                if self.enabled and self.started
                else "CONFIGURED"
                if self.enabled
                else "DISABLED"
            ),
            "enabled": self.enabled,
            "started": self.started,
            "auto_load": self.auto_load,
            "auto_save": self.auto_save,
            "loaded": self.loaded,
            "initial_balance": self.initial_balance,
            "repository": self.repository.status(),
            "account": self.account.status(),
            "execution_authorized": False,
            "live_execution": False,
            "last_report": dict(self.last_report),
        }


paper_account_runtime = PaperAccountRuntime()
