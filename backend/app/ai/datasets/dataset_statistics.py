from __future__ import annotations

from typing import Any

import pandas as pd


class DatasetStatistics:
    """Produz um resumo serializável de um pandas.DataFrame."""

    def summary(self, dataframe: pd.DataFrame) -> dict[str, Any]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe deve ser um pandas.DataFrame.")

        missing_by_column = {
            str(column): int(value)
            for column, value in dataframe.isna().sum().items()
            if int(value) > 0
        }

        target_distribution: dict[str, int] = {}
        if "success" in dataframe.columns:
            counts = dataframe["success"].value_counts(dropna=False)
            for key, value in counts.items():
                label = "unlabeled" if pd.isna(key) else str(int(key))
                target_distribution[label] = int(value)

        numeric_columns = [
            str(column)
            for column in dataframe.select_dtypes(include="number").columns
        ]

        return {
            "rows": len(dataframe),
            "columns": len(dataframe.columns),
            "column_names": [str(column) for column in dataframe.columns],
            "numeric_columns": numeric_columns,
            "missing": int(dataframe.isna().sum().sum()),
            "missing_by_column": missing_by_column,
            "duplicates": int(dataframe.duplicated().sum()),
            "target_distribution": target_distribution,
            "memory_bytes": int(dataframe.memory_usage(deep=True).sum()),
        }



dataset_statistics = DatasetStatistics()
