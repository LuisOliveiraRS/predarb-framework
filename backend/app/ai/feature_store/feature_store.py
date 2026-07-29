from __future__ import annotations

from copy import deepcopy
from threading import RLock
from typing import Any

from app.ai.feature_store.feature import Feature


class FeatureStore:
    """
    Armazenamento em memória, thread-safe, para vetores e features.

    A camada não é um banco persistente. Ela serve como cache de análise e
    nunca expõe referências mutáveis do armazenamento interno.
    """

    def __init__(self) -> None:
        self._features: dict[str, Any] = {}
        self._lock = RLock()

    @staticmethod
    def _key(key: Any) -> str:
        normalized = str(key or "").strip()
        if not normalized:
            raise ValueError("A chave da feature não pode ser vazia.")
        return normalized

    @staticmethod
    def _copy(value: Any) -> Any:
        try:
            return deepcopy(value)
        except Exception:
            return value

    @property
    def features(self) -> dict[str, Any]:
        return self.all()

    def put(self, key: Any, value: Any) -> Any:
        normalized_key = self._key(key)
        stored = self._copy(value)

        with self._lock:
            self._features[normalized_key] = stored

        return value

    def put_feature(self, feature: Feature) -> Feature:
        if not isinstance(feature, Feature):
            raise TypeError("feature deve ser uma instância de Feature.")

        self.put(feature.name, feature)
        return feature

    def get(self, key: Any, default: Any = None) -> Any:
        normalized_key = self._key(key)

        with self._lock:
            if normalized_key not in self._features:
                return self._copy(default)

            return self._copy(self._features[normalized_key])

    def require(self, key: Any) -> Any:
        normalized_key = self._key(key)

        with self._lock:
            if normalized_key not in self._features:
                raise KeyError(f"Feature não encontrada: {normalized_key}")

            return self._copy(self._features[normalized_key])

    def exists(self, key: Any) -> bool:
        normalized_key = self._key(key)
        with self._lock:
            return normalized_key in self._features

    def remove(self, key: Any) -> Any:
        normalized_key = self._key(key)
        with self._lock:
            value = self._features.pop(normalized_key, None)
        return self._copy(value)

    def all(self) -> dict[str, Any]:
        with self._lock:
            return self._copy(self._features)

    def count(self) -> int:
        with self._lock:
            return len(self._features)

    def clear(self) -> None:
        with self._lock:
            self._features.clear()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "type": "memory",
                "count": len(self._features),
                "keys": sorted(self._features),
            }


feature_store = FeatureStore()
