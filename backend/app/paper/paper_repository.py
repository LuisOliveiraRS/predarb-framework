from __future__ import annotations

import json
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from threading import RLock
from typing import Any, Mapping


class PaperAccountRepository:
    SCHEMA_VERSION = 1

    def __init__(self, path: str | Path = "paper_data/paper_account.json") -> None:
        self.path = Path(path)
        if self.path.suffix.lower() != ".json":
            raise ValueError("O arquivo da conta paper deve usar extensão .json.")
        self._lock = RLock()
        self.last_saved_at: str | None = None
        self.last_loaded_at: str | None = None

    def exists(self) -> bool:
        return self.path.is_file()

    def save(self, state: Mapping[str, Any]) -> Path:
        payload = {
            "schema_version": self.SCHEMA_VERSION,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "account": deepcopy(dict(state)),
        }
        encoded = json.dumps(
            payload,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        with self._lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temporary = self.path.with_suffix(self.path.suffix + ".tmp")
            temporary.write_text(encoded, encoding="utf-8")
            temporary.replace(self.path)
            self.last_saved_at = payload["saved_at"]
        return self.path

    def load(self) -> dict[str, Any] | None:
        if not self.exists():
            return None
        with self._lock:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        if payload.get("schema_version") != self.SCHEMA_VERSION:
            raise ValueError("Versão incompatível do arquivo da conta paper.")
        account = payload.get("account")
        if not isinstance(account, Mapping):
            raise ValueError("Arquivo da conta paper não contém estado válido.")
        self.last_loaded_at = datetime.now(timezone.utc).isoformat()
        return deepcopy(dict(account))

    def remove(self) -> bool:
        with self._lock:
            if not self.path.exists():
                return False
            self.path.unlink()
            return True

    def status(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "exists": self.exists(),
            "schema_version": self.SCHEMA_VERSION,
            "last_saved_at": self.last_saved_at,
            "last_loaded_at": self.last_loaded_at,
            "serializer": "json",
            "atomic_write": True,
            "live_execution": False,
        }
