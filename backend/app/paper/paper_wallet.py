from __future__ import annotations

from math import isfinite
from threading import RLock
from typing import Any, Mapping


class PaperWallet:
    """Carteira virtual thread-safe, sem qualquer integração com execução live."""

    def __init__(self, initial_balance: float = 10_000.0) -> None:
        self._lock = RLock()
        self.initial_balance = self._amount(initial_balance, "initial_balance")
        if self.initial_balance <= 0:
            raise ValueError("initial_balance deve ser maior que zero.")
        self.balance = self.initial_balance
        self.locked = 0.0

    @staticmethod
    def _amount(value: Any, field_name: str) -> float:
        if isinstance(value, bool):
            raise TypeError(f"{field_name} não pode ser booleano.")
        try:
            amount = float(value)
        except (TypeError, ValueError) as exc:
            raise TypeError(f"{field_name} deve ser numérico.") from exc
        if not isfinite(amount):
            raise ValueError(f"{field_name} deve ser finito.")
        return amount

    def available(self) -> float:
        with self._lock:
            return round(max(0.0, self.balance - self.locked), 8)

    def reserve(self, amount: Any) -> bool:
        resolved = self._amount(amount, "amount")
        if resolved < 0:
            raise ValueError("amount não pode ser negativo.")
        with self._lock:
            if resolved > self.available() + 1e-9:
                return False
            self.locked += resolved
            return True

    def release(self, amount: Any) -> float:
        resolved = self._amount(amount, "amount")
        if resolved < 0:
            raise ValueError("amount não pode ser negativo.")
        with self._lock:
            self.locked = max(0.0, self.locked - resolved)
            return round(self.locked, 8)

    def deposit(self, amount: Any) -> float:
        resolved = self._amount(amount, "amount")
        if resolved < 0:
            raise ValueError("amount não pode ser negativo.")
        with self._lock:
            self.balance += resolved
            return round(self.balance, 8)

    def withdraw(self, amount: Any) -> float:
        resolved = self._amount(amount, "amount")
        if resolved < 0:
            raise ValueError("amount não pode ser negativo.")
        with self._lock:
            if resolved > self.available() + 1e-9:
                raise ValueError("Saldo paper insuficiente.")
            self.balance -= resolved
            return round(self.balance, 8)

    def reset(self, initial_balance: Any | None = None) -> None:
        with self._lock:
            if initial_balance is not None:
                resolved = self._amount(initial_balance, "initial_balance")
                if resolved <= 0:
                    raise ValueError("initial_balance deve ser maior que zero.")
                self.initial_balance = resolved
            self.balance = self.initial_balance
            self.locked = 0.0

    def snapshot(self) -> dict[str, float]:
        with self._lock:
            return {
                "initial_balance": round(self.initial_balance, 8),
                "balance": round(self.balance, 8),
                "cash": round(self.balance, 8),
                "locked": round(self.locked, 8),
                "available": self.available(),
            }

    def restore(self, data: Mapping[str, Any]) -> None:
        initial = self._amount(data.get("initial_balance", 10_000), "initial_balance")
        balance = self._amount(data.get("balance", data.get("cash", initial)), "balance")
        locked = self._amount(data.get("locked", 0.0), "locked")
        if initial <= 0 or balance < 0 or locked < 0 or locked > balance + 1e-9:
            raise ValueError("Estado inválido da PaperWallet.")
        with self._lock:
            self.initial_balance = initial
            self.balance = balance
            self.locked = locked

    to_dict = snapshot


paper_wallet = PaperWallet()
