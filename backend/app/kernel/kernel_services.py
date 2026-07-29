from __future__ import annotations

from threading import RLock
from typing import Any


class KernelServices:
    """
    Registro central de serviços do Kernel.

    Responsabilidades:

    - registrar serviços;
    - recuperar serviços pelo nome;
    - validar serviços obrigatórios;
    - remover registros;
    - fornecer informações para monitoramento.

    O atributo público ``services`` foi mantido
    para preservar compatibilidade com o Kernel.
    """

    def __init__(self) -> None:
        self.services: dict[str, Any] = {}
        self._lock = RLock()

    @staticmethod
    def _normalize_name(name: str) -> str:
        """
        Valida e normaliza o nome de um serviço.
        """

        if not isinstance(name, str):
            raise TypeError(
                "O nome do serviço deve ser uma string."
            )

        normalized_name = name.strip()

        if not normalized_name:
            raise ValueError(
                "O nome do serviço não pode ser vazio."
            )

        return normalized_name

    def register(
        self,
        name: str,
        service: Any,
        *,
        replace: bool = True,
    ) -> Any:
        """
        Registra um serviço.

        Por padrão, preserva o comportamento anterior
        e substitui um serviço que já use o mesmo nome.

        Use ``replace=False`` para impedir substituições.
        """

        normalized_name = self._normalize_name(
            name,
        )

        if service is None:
            raise ValueError(
                "Não é possível registrar um serviço None."
            )

        with self._lock:
            if (
                not replace
                and normalized_name in self.services
            ):
                raise KeyError(
                    "Já existe um serviço registrado "
                    f"com o nome: {normalized_name}"
                )

            self.services[normalized_name] = service

        return service

    def get(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um serviço registrado.

        Retorna ``default`` quando o serviço não existir.
        """

        normalized_name = self._normalize_name(
            name,
        )

        with self._lock:
            return self.services.get(
                normalized_name,
                default,
            )

    def require(
        self,
        name: str,
    ) -> Any:
        """
        Recupera um serviço obrigatório.

        Gera LookupError quando o serviço
        não estiver registrado.
        """

        normalized_name = self._normalize_name(
            name,
        )

        with self._lock:
            service = self.services.get(
                normalized_name,
            )

        if service is None:
            raise LookupError(
                "Serviço obrigatório não registrado "
                f"no Kernel: {normalized_name}"
            )

        return service

    def exists(
        self,
        name: str,
    ) -> bool:
        """
        Verifica se um serviço está registrado.
        """

        normalized_name = self._normalize_name(
            name,
        )

        with self._lock:
            return (
                normalized_name
                in self.services
            )

    def unregister(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Remove um serviço do registro.
        """

        normalized_name = self._normalize_name(
            name,
        )

        with self._lock:
            return self.services.pop(
                normalized_name,
                default,
            )

    def remove(
        self,
        name: str,
        default: Any = None,
    ) -> Any:
        """
        Alias para unregister.
        """

        return self.unregister(
            name,
            default,
        )

    def all(self) -> list[Any]:
        """
        Retorna todos os serviços registrados.
        """

        with self._lock:
            return list(
                self.services.values(),
            )

    def names(self) -> list[str]:
        """
        Retorna os nomes dos serviços registrados.
        """

        with self._lock:
            return list(
                self.services.keys(),
            )

    def items(self) -> list[tuple[str, Any]]:
        """
        Retorna pares de nome e serviço.
        """

        with self._lock:
            return list(
                self.services.items(),
            )

    def snapshot(self) -> dict[str, Any]:
        """
        Retorna uma cópia do registro atual.
        """

        with self._lock:
            return dict(
                self.services,
            )

    def clear(self) -> None:
        """
        Remove todos os serviços registrados.

        Este método apenas limpa o registro.
        Ele não executa stop(), close() ou shutdown()
        nos serviços, pois seus ciclos de vida são
        controlados pelo application.py.
        """

        with self._lock:
            self.services.clear()

    def __contains__(
        self,
        name: object,
    ) -> bool:
        if not isinstance(name, str):
            return False

        return self.exists(
            name,
        )

    def __len__(self) -> int:
        with self._lock:
            return len(
                self.services,
            )

    def __iter__(self):
        """
        Itera sobre os nomes dos serviços usando
        uma cópia para evitar alterações durante
        a iteração.
        """

        return iter(
            self.names(),
        )


kernel_services = KernelServices()