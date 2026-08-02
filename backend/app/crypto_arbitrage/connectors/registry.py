"""Registro de conectores cripto, fail-closed por construção.

A guarda central desta fase: o registry recusa qualquer objeto
que exponha capacidade de execução, mesmo que o chamador peça
explicitamente. Não há flag, parâmetro ou caminho alternativo que
permita registrar um `TradingAdapter`.

A recusa é por inspeção de capacidade, não por tipo declarado.
Um objeto que apenas *pareça* capaz de enviar ordem já é
suficiente para bloquear o registro.
"""

from __future__ import annotations

from typing import Any

from app.crypto_arbitrage.connectors.base import (
    DexQuoteConnector,
    PrivateAccountReader,
    PublicCexConnector,
)
from app.crypto_arbitrage.domain.errors import (
    ConnectorAlreadyRegisteredError,
    ConnectorNotFoundError,
    ExecutionNotAuthorizedError,
)


EXECUTION_CAPABILITIES: tuple[str, ...] = (
    "submit_order",
    "cancel_order",
    "place_order",
    "create_order",
    "amend_order",
    "withdraw",
    "transfer",
    "sign_transaction",
    "send_transaction",
)


def assert_no_execution_capability(
    connector: Any,
) -> None:
    """Recusa conector com qualquer capacidade de execução.

    Invariantes da seção 8 do CLAUDE.md: execução financeira
    permanece desativada, e IA não autoriza ordem sozinha.
    """

    found = sorted(
        name
        for name in EXECUTION_CAPABILITIES
        if callable(getattr(connector, name, None))
    )

    if found:
        raise ExecutionNotAuthorizedError(
            "Conector recusado: expõe capacidade de "
            f"execução ({', '.join(found)}). A Fase 18 é "
            "read-only e nenhum adapter de execução pode "
            "ser registrado."
        )


class ConnectorRegistry:
    """Guarda conectores read-only por identificador de venue."""

    def __init__(self) -> None:
        self._public: dict[str, PublicCexConnector] = {}
        self._accounts: dict[str, PrivateAccountReader] = {}
        self._dex: dict[str, DexQuoteConnector] = {}

    @staticmethod
    def _key(venue_id: str) -> str:
        normalized = str(venue_id or "").strip().upper()

        if not normalized:
            raise ConnectorNotFoundError(
                "venue_id é obrigatório."
            )

        return normalized

    def _register(
        self,
        bucket: dict[str, Any],
        connector: Any,
        *,
        label: str,
    ) -> None:
        assert_no_execution_capability(connector)

        key = self._key(
            getattr(connector, "venue_id", "")
        )

        if key in bucket:
            raise ConnectorAlreadyRegisteredError(
                f"Já existe {label} registrado para {key}."
            )

        bucket[key] = connector

    def register_public(
        self,
        connector: PublicCexConnector,
    ) -> None:
        self._register(
            self._public,
            connector,
            label="conector público",
        )

    def register_account_reader(
        self,
        connector: PrivateAccountReader,
    ) -> None:
        self._register(
            self._accounts,
            connector,
            label="leitor de conta",
        )

    def register_dex_quoter(
        self,
        connector: DexQuoteConnector,
    ) -> None:
        self._register(
            self._dex,
            connector,
            label="cotador DEX",
        )

    def register_trading_adapter(
        self,
        connector: Any,
    ) -> None:
        """Sempre levanta erro. Existe para ser explícito.

        Um chamador que procure como registrar execução encontra
        este método e a recusa, em vez de improvisar um caminho
        próprio.
        """

        raise ExecutionNotAuthorizedError(
            "Registro de adapter de execução é proibido. "
            "Exige autorização explícita e o checklist "
            "completo da seção 26 do CLAUDE.md."
        )

    def get_public(
        self,
        venue_id: str,
    ) -> PublicCexConnector:
        key = self._key(venue_id)

        if key not in self._public:
            raise ConnectorNotFoundError(
                f"Nenhum conector público para {key}."
            )

        return self._public[key]

    def get_account_reader(
        self,
        venue_id: str,
    ) -> PrivateAccountReader:
        key = self._key(venue_id)

        if key not in self._accounts:
            raise ConnectorNotFoundError(
                f"Nenhum leitor de conta para {key}."
            )

        return self._accounts[key]

    def get_dex_quoter(
        self,
        venue_id: str,
    ) -> DexQuoteConnector:
        key = self._key(venue_id)

        if key not in self._dex:
            raise ConnectorNotFoundError(
                f"Nenhum cotador DEX para {key}."
            )

        return self._dex[key]

    def public_venues(self) -> list[str]:
        return sorted(self._public)

    def status(self) -> dict[str, Any]:
        """Resumo auditável do registro."""

        return {
            "public_connectors": sorted(self._public),
            "account_readers": sorted(self._accounts),
            "dex_quoters": sorted(self._dex),
            "trading_adapters": [],
            "market_data_only": True,
            "read_only": True,
            "execution_authorized": False,
            "financial_execution": False,
            "automatic_execution_authorized": False,
            "order_submission_available": False,
            "exchange_endpoint_available": False,
            "wallet_signing": False,
            "private_key_access": False,
        }

    def clear(self) -> None:
        self._public.clear()
        self._accounts.clear()
        self._dex.clear()


connector_registry = ConnectorRegistry()
