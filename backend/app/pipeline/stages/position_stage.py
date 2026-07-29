from __future__ import annotations

from collections.abc import Mapping
from typing import Any

from app.pipeline.pipeline_stage import PipelineStage
from app.positions.position_manager import (
    position_manager,
)


class PositionStage(PipelineStage):
    """
    Anexa ao contexto um snapshot das posições.

    Este estágio não cria posições. A criação deve
    ocorrer somente após uma execução confirmada.
    """

    def __init__(
        self,
        *,
        only_open: bool = True,
    ) -> None:
        self.only_open = bool(
            only_open,
        )

    @staticmethod
    def _read_field(
        target: Any,
        field_name: str,
        default: Any = None,
    ) -> Any:
        if isinstance(target, Mapping):
            return target.get(
                field_name,
                default,
            )

        if target is None:
            return default

        return getattr(
            target,
            field_name,
            default,
        )

    @classmethod
    def _is_open(
        cls,
        position: Any,
    ) -> bool:
        status = cls._read_field(
            position,
            "status",
            None,
        )

        if status is not None:
            status_value = cls._read_field(
                status,
                "value",
                status,
            )

            return (
                str(status_value)
                .strip()
                .upper()
                == "OPEN"
            )

        return not bool(
            cls._read_field(
                position,
                "closed",
                False,
            )
        )

    def process(
        self,
        context: Any,
    ) -> Any:
        if self.only_open:
            positions = list(
                position_manager.open()
                or [],
            )

        else:
            positions = list(
                position_manager.all()
                or [],
            )

        context.positions = positions

        context.metadata["positions"] = {
            "mode": (
                "open"
                if self.only_open
                else "all"
            ),
            "count": len(positions),
            "open": sum(
                1
                for position in positions
                if self._is_open(
                    position,
                )
            ),
        }

        return context

    execute = process