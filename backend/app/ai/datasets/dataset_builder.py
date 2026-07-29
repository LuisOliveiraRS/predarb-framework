from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

import pandas as pd

from app.ai.feature_store.feature_builder import FeatureBuilder, feature_builder


class DatasetBuilder:
    """
    Constrói datasets tabulares a partir de oportunidades históricas.

    O target nunca recebe sucesso=1 por padrão. Amostras sem resultado real
    permanecem sem rótulo, evitando criar um dataset artificialmente positivo.
    """

    TARGET_COLUMN = "success"

    def __init__(
        self,
        *,
        features: FeatureBuilder | None = None,
    ) -> None:
        self.features = features or feature_builder
        self.last_report: dict[str, Any] = {}

    @staticmethod
    def _read(target: Any, field: str, default: Any = None) -> Any:
        if isinstance(target, Mapping):
            return target.get(field, default)
        if target is None:
            return default
        return getattr(target, field, default)

    @classmethod
    def _target(cls, opportunity: Any) -> int | None:
        explicit = cls._read(opportunity, cls.TARGET_COLUMN, None)

        if explicit is not None:
            if isinstance(explicit, bool):
                return int(explicit)

            try:
                numeric = int(explicit)
            except (TypeError, ValueError) as exc:
                raise ValueError("O target success deve ser 0 ou 1.") from exc

            if numeric not in {0, 1}:
                raise ValueError("O target success deve ser 0 ou 1.")

            return numeric

        status = str(cls._read(opportunity, "status", "") or "").strip().upper()

        if status in {"SUCCESS", "FILLED", "COMPLETED", "SETTLED", "WON"}:
            return 1

        if status in {
            "FAILED",
            "REJECTED",
            "CANCELLED",
            "CANCELED",
            "LOST",
        }:
            return 0

        return None

    def build(
        self,
        opportunities: Iterable[Any],
        *,
        include_target: bool = True,
        drop_unlabeled: bool = False,
        strict_features: bool = False,
    ) -> pd.DataFrame:
        if isinstance(opportunities, (str, bytes, Mapping)):
            raise TypeError("opportunities deve ser uma coleção.")

        rows: list[dict[str, Any]] = []
        unlabeled = 0

        for opportunity in opportunities:
            row: dict[str, Any] = self.features.build(
                opportunity,
                strict=strict_features,
            )

            if include_target:
                target = self._target(opportunity)
                if target is None:
                    unlabeled += 1
                    if drop_unlabeled:
                        continue
                    row[self.TARGET_COLUMN] = pd.NA
                else:
                    row[self.TARGET_COLUMN] = target

            rows.append(row)

        columns = list(FeatureBuilder.FEATURE_NAMES)
        if include_target:
            columns.append(self.TARGET_COLUMN)

        dataframe = pd.DataFrame(rows, columns=columns)

        for column in FeatureBuilder.FEATURE_NAMES:
            dataframe[column] = pd.to_numeric(dataframe[column], errors="coerce")

        if include_target and self.TARGET_COLUMN in dataframe:
            dataframe[self.TARGET_COLUMN] = dataframe[self.TARGET_COLUMN].astype(
                "Int64"
            )

        self.last_report = {
            "input": len(rows) + (unlabeled if drop_unlabeled else 0),
            "rows": len(dataframe),
            "features": len(FeatureBuilder.FEATURE_NAMES),
            "include_target": bool(include_target),
            "unlabeled": unlabeled,
            "dropped_unlabeled": unlabeled if drop_unlabeled else 0,
        }

        return dataframe



dataset_builder = DatasetBuilder()
