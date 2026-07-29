from __future__ import annotations

from collections.abc import Mapping
from threading import RLock
from typing import Any


class KernelContext:
    """
    Contexto compartilhado entre os componentes
    do PredArb Framework.

    O contexto permite:

    - registrar dependências globais;
    - recuperar dependências pelo nome;
    - utilizar acesso por atributo;
    - remover valores;
    - gerar diagnósticos do estado atual.

    Exemplos:

        kernel_context.set("database", database)

        database = kernel_context.get("database")

        kernel_context.cache = cache

        cache = kernel_context.cache
    """

    DEFAULT_KEYS = (
        "market_engine",
        "strategy_engine",
        "execution_engine",
        "portfolio_manager",
        "exchange_manager",
        "metrics",
        "database",
        "cache",
    )

    def __init__(self) -> None:
        object.__setattr__(
            self,
            "_lock",
            RLock(),
        )

        object.__setattr__(
            self,
            "_values",
            {
                key: None
                for key in self.DEFAULT_KEYS
            },
        )

    @staticmethod
    def _normalize_key(key: str) -> str:
        """
        Valida e normaliza uma chave do contexto.
        """

        if not isinstance(key, str):
            raise TypeError(
                "A chave do KernelContext deve ser uma string."
            )

        normalized_key = key.strip()

        if not normalized_key:
            raise ValueError(
                "A chave do KernelContext não pode ser vazia."
            )

        return normalized_key

    def set(
        self,
        key: str,
        value: Any,
    ) -> Any:
        """
        Registra ou substitui um valor no contexto.
        """

        normalized_key = self._normalize_key(
            key,
        )

        with self._lock:
            self._values[normalized_key] = value

        return value

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um valor registrado.

        Retorna o valor informado em ``default``
        quando a chave não estiver registrada.
        """

        normalized_key = self._normalize_key(
            key,
        )

        with self._lock:
            return self._values.get(
                normalized_key,
                default,
            )

    def require(
        self,
        key: str,
    ) -> Any:
        """
        Recupera uma dependência obrigatória.

        Gera LookupError quando a chave não existir
        ou quando o valor estiver definido como None.
        """

        normalized_key = self._normalize_key(
            key,
        )

        with self._lock:
            value = self._values.get(
                normalized_key,
            )

        if value is None:
            raise LookupError(
                "Dependência obrigatória não encontrada "
                f"no KernelContext: {normalized_key}"
            )

        return value

    def exists(
        self,
        key: str,
        *,
        require_value: bool = False,
    ) -> bool:
        """
        Verifica se uma chave está registrada.

        Quando ``require_value`` for True, a chave
        somente será considerada existente caso seu
        valor seja diferente de None.
        """

        normalized_key = self._normalize_key(
            key,
        )

        with self._lock:
            if normalized_key not in self._values:
                return False

            if require_value:
                return (
                    self._values[normalized_key]
                    is not None
                )

            return True

    def remove(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Remove uma chave dinâmica do contexto.

        As chaves padrão não são eliminadas:
        seu valor volta a ser None.
        """

        normalized_key = self._normalize_key(
            key,
        )

        with self._lock:
            if normalized_key in self.DEFAULT_KEYS:
                previous_value = self._values.get(
                    normalized_key,
                    default,
                )

                self._values[normalized_key] = None

                return previous_value

            return self._values.pop(
                normalized_key,
                default,
            )

    def update(
        self,
        values: Mapping[str, Any] | None = None,
        **kwargs: Any,
    ) -> None:
        """
        Registra múltiplos valores no contexto.
        """

        entries: dict[str, Any] = {}

        if values is not None:
            entries.update(
                dict(values),
            )

        entries.update(
            kwargs,
        )

        for key, value in entries.items():
            self.set(
                key,
                value,
            )

    def clear(
        self,
        *,
        keep_defaults: bool = True,
    ) -> None:
        """
        Limpa o contexto.

        Por padrão, mantém as chaves oficiais com
        valor None para preservar compatibilidade.
        """

        with self._lock:
            self._values.clear()

            if keep_defaults:
                self._values.update(
                    {
                        key: None
                        for key in self.DEFAULT_KEYS
                    }
                )

    def keys(self) -> list[str]:
        """
        Retorna os nomes registrados.
        """

        with self._lock:
            return list(
                self._values.keys(),
            )

    def items(self) -> list[tuple[str, Any]]:
        """
        Retorna os registros do contexto.
        """

        with self._lock:
            return list(
                self._values.items(),
            )

    def snapshot(self) -> dict[str, Any]:
        """
        Retorna uma cópia do contexto atual.
        """

        with self._lock:
            return dict(
                self._values,
            )

    def to_dict(self) -> dict[str, Any]:
        """
        Alias de snapshot para serialização
        e diagnóstico.
        """

        return self.snapshot()

    def __getattr__(
        self,
        name: str,
    ) -> Any:
        """
        Permite recuperar valores como atributos.

        Exemplo:

            kernel_context.database
        """

        values = object.__getattribute__(
            self,
            "_values",
        )

        lock = object.__getattribute__(
            self,
            "_lock",
        )

        with lock:
            if name in values:
                return values[name]

        raise AttributeError(
            f"{self.__class__.__name__!s} "
            f"não possui o atributo {name!r}."
        )

    def __setattr__(
        self,
        name: str,
        value: Any,
    ) -> None:
        """
        Permite registrar valores como atributos.

        Exemplo:

            kernel_context.database = database
        """

        if name.startswith("_"):
            object.__setattr__(
                self,
                name,
                value,
            )
            return

        self.set(
            name,
            value,
        )

    def __contains__(
        self,
        key: object,
    ) -> bool:
        if not isinstance(key, str):
            return False

        return self.exists(
            key,
        )

    def __len__(self) -> int:
        with self._lock:
            return len(
                self._values,
            )


kernel_context = KernelContext()