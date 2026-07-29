from __future__ import annotations

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


_UNSET = object()


class PipelineContext:
    """
    Estado compartilhado entre os estágios
    do Pipeline.

    O contexto aceita:

    - mercados;
    - snapshots;
    - sinais;
    - oportunidades;
    - ordens;
    - venues;
    - relatórios de execução;
    - posições;
    - metadados;
    - erros;
    - histórico dos estágios.
    """

    def __init__(
        self,
        data: Any = None,
        **values: Any,
    ) -> None:
        now = datetime.now(
            timezone.utc,
        )

        self.input_data: Any = data
        self.data: Any = data
        self._output_data: Any = _UNSET

        # Mercados
        self.markets: list[Any] | None = None
        self.market_snapshot: Any = None

        # Sinais
        self.signal: Any = None
        self.signals: list[Any] | None = None

        # Oportunidades
        self.opportunity: Any = None
        self.opportunities: list[Any] | None = None

        # Ordens e venue
        self.order: Any = None
        self.orders: list[Any] | None = None
        self.venue: Any = None

        # Execução
        self.execution_report: Any = None

        self.execution_reports: (
            list[Any] | None
        ) = None

        # Posições
        self.position: Any = None
        self.positions: list[Any] | None = None

        # Controle
        self.metadata: dict[str, Any] = {}
        self.errors: list[dict[str, Any]] = []

        self.stage_history: (
            list[dict[str, Any]]
        ) = []

        self.current_stage: str | None = None

        self.halted: bool = False
        self.halt_reason: str | None = None

        self.started_at: datetime = now
        self.finished_at: datetime | None = None

        self._initialize_data(
            data,
        )

        for key, value in values.items():
            setattr(
                self,
                key,
                value,
            )

    @classmethod
    def ensure(
        cls,
        value: Any,
    ) -> PipelineContext:
        """
        Retorna um contexto existente ou cria
        um novo contexto.
        """

        if isinstance(
            value,
            cls,
        ):
            return value

        from app.pipeline.pipeline_result import (
            PipelineResult,
        )

        if isinstance(
            value,
            PipelineResult,
        ):
            return value.context

        return cls(
            value,
        )

    @staticmethod
    def _read_field(
        value: Any,
        field_name: str,
    ) -> Any:
        """
        Recupera campos de dicionários
        ou objetos.
        """

        if isinstance(
            value,
            Mapping,
        ):
            return value.get(
                field_name,
            )

        return getattr(
            value,
            field_name,
            None,
        )

    @classmethod
    def _looks_like_opportunity(
        cls,
        value: Any,
    ) -> bool:
        """
        Verifica se o valor aparenta ser
        uma oportunidade.
        """

        opportunity_fields = (
            "roi",
            "profit",
            "cost",
            "buy_yes_platform",
            "buy_no_platform",
            "expected_return",
        )

        return any(
            cls._read_field(
                value,
                field_name,
            )
            is not None
            for field_name
            in opportunity_fields
        )

    @classmethod
    def _looks_like_market(
        cls,
        value: Any,
    ) -> bool:
        """
        Verifica se o valor aparenta ser
        um mercado.
        """

        required_fields = (
            "question",
            "yes",
            "no",
        )

        return all(
            cls._read_field(
                value,
                field_name,
            )
            is not None
            for field_name
            in required_fields
        )

    def _initialize_data(
        self,
        data: Any,
    ) -> None:
        """
        Classifica automaticamente a entrada
        quando possível.
        """

        if data is None:
            return

        if isinstance(
            data,
            Mapping,
        ):
            known_fields = {
                "markets",
                "market_snapshot",
                "signal",
                "signals",
                "opportunity",
                "opportunities",
                "order",
                "orders",
                "venue",
                "execution_report",
                "execution_reports",
                "position",
                "positions",
                "metadata",
            }

            matched_fields = (
                known_fields.intersection(
                    data.keys(),
                )
            )

            if matched_fields:
                for field_name in matched_fields:
                    setattr(
                        self,
                        field_name,
                        data[field_name],
                    )

                return

            if self._looks_like_opportunity(
                data,
            ):
                self.opportunity = data
                self.opportunities = [
                    data,
                ]

                return

            if self._looks_like_market(
                data,
            ):
                self.market_snapshot = data
                self.markets = [
                    data,
                ]

                return

            return

        if (
            isinstance(
                data,
                Sequence,
            )
            and not isinstance(
                data,
                (str, bytes),
            )
        ):
            items = list(
                data,
            )

            self.data = items

            if not items:
                self.opportunities = []
                return

            first_item = items[0]

            if self._looks_like_opportunity(
                first_item,
            ):
                self.opportunities = items
                return

            if self._looks_like_market(
                first_item,
            ):
                self.markets = items
                return

    @property
    def output(self) -> Any:
        """
        Retorna o resultado mais específico
        disponível no contexto.
        """

        if self._output_data is not _UNSET:
            return self._output_data

        if self.execution_report is not None:
            return self.execution_report

        if self.execution_reports is not None:
            return self.execution_reports

        if self.orders is not None:
            return self.orders

        if self.positions is not None:
            return self.positions

        if self.opportunities is not None:
            return self.opportunities

        if self.markets is not None:
            return self.markets

        return self.data

    def set_output(
        self,
        value: Any,
    ) -> Any:
        """
        Define explicitamente o resultado
        produzido pelo Pipeline.
        """

        self._output_data = value
        self.data = value

        return value

    def clear_output(self) -> None:
        """
        Remove o resultado explícito.
        """

        self._output_data = _UNSET

    def halt(
        self,
        reason: str,
    ) -> None:
        """
        Interrompe os próximos estágios
        sem lançar uma exceção.
        """

        self.halted = True
        self.halt_reason = str(
            reason,
        )

    def add_error(
        self,
        stage: str,
        error: BaseException,
    ) -> dict[str, Any]:
        """
        Registra uma falha ocorrida em
        um estágio.
        """

        record = {
            "stage": stage,
            "type": (
                error.__class__.__name__
            ),
            "message": str(
                error,
            ),
            "timestamp": datetime.now(
                timezone.utc,
            ).isoformat(),
        }

        self.errors.append(
            record,
        )

        return record

    def add_stage_record(
        self,
        *,
        stage: str,
        status: str,
        duration_ms: float,
        detail: str | None = None,
    ) -> dict[str, Any]:
        """
        Registra o resultado e a duração
        de um estágio.
        """

        record: dict[str, Any] = {
            "stage": stage,
            "status": status,
            "duration_ms": round(
                max(
                    0.0,
                    float(duration_ms),
                ),
                3,
            ),
        }

        if detail:
            record["detail"] = str(
                detail,
            )

        self.stage_history.append(
            record,
        )

        return record

    def complete(self) -> None:
        """
        Finaliza o ciclo do contexto.
        """

        self.current_stage = None

        self.finished_at = datetime.now(
            timezone.utc,
        )

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:
        """
        Recupera um valor do contexto.
        """

        return getattr(
            self,
            key,
            default,
        )

    def set(
        self,
        key: str,
        value: Any,
    ) -> Any:
        """
        Registra um valor no contexto.
        """

        if (
            not isinstance(
                key,
                str,
            )
            or not key.strip()
        ):
            raise ValueError(
                "A chave do PipelineContext "
                "deve ser uma string válida."
            )

        setattr(
            self,
            key.strip(),
            value,
        )

        return value

    def to_dict(self) -> dict[str, Any]:
        """
        Retorna um retrato completo
        do contexto.
        """

        return {
            "input_data": self.input_data,
            "data": self.data,
            "output": self.output,
            "markets": self.markets,
            "market_snapshot": (
                self.market_snapshot
            ),
            "signal": self.signal,
            "signals": self.signals,
            "opportunity": self.opportunity,
            "opportunities": self.opportunities,
            "order": self.order,
            "orders": self.orders,
            "venue": self.venue,
            "execution_report": (
                self.execution_report
            ),
            "execution_reports": (
                self.execution_reports
            ),
            "position": self.position,
            "positions": self.positions,
            "metadata": dict(
                self.metadata,
            ),
            "errors": list(
                self.errors,
            ),
            "stage_history": list(
                self.stage_history,
            ),
            "halted": self.halted,
            "halt_reason": self.halt_reason,
            "started_at": (
                self.started_at.isoformat()
            ),
            "finished_at": (
                self.finished_at.isoformat()
                if self.finished_at is not None
                else None
            ),
        }