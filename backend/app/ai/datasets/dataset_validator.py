from __future__ import annotations

from typing import Any

import pandas as pd

from app.ai.feature_store.feature_builder import FeatureBuilder


class DatasetValidator:
    """Valida schema, tipos, valores ausentes e target do dataset."""

    def __init__(self) -> None:
        self.last_report: dict[str, Any] = {}

    def evaluate(
        self,
        dataframe: pd.DataFrame,
        *,
        require_target: bool = False,
        allow_missing_features: bool = False,
        allow_unlabeled: bool = False,
    ) -> dict[str, Any]:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe deve ser um pandas.DataFrame.")

        errors: list[str] = []
        warnings: list[str] = []

        if dataframe.empty:
            errors.append("DATASET_EMPTY")

        required_features = list(FeatureBuilder.FEATURE_NAMES)
        missing_columns = [
            column for column in required_features if column not in dataframe.columns
        ]

        if missing_columns:
            errors.append("FEATURE_COLUMNS_MISSING")

        invalid_numeric_columns: list[str] = []
        missing_feature_values: dict[str, int] = {}

        for column in required_features:
            if column not in dataframe.columns:
                continue

            converted = pd.to_numeric(dataframe[column], errors="coerce")
            invalid_count = int(converted.isna().sum())

            if invalid_count:
                missing_feature_values[column] = invalid_count
                if not allow_missing_features:
                    invalid_numeric_columns.append(column)

        if invalid_numeric_columns:
            errors.append("FEATURE_VALUES_INVALID")

        target_missing = "success" not in dataframe.columns
        unlabeled = 0
        invalid_targets: list[Any] = []

        if require_target and target_missing:
            errors.append("TARGET_MISSING")

        if not target_missing:
            target = pd.to_numeric(dataframe["success"], errors="coerce")
            unlabeled = int(target.isna().sum())

            invalid_targets = sorted(
                set(target.dropna().tolist()) - {0, 1}
            )

            if invalid_targets:
                errors.append("TARGET_INVALID")

            if require_target and unlabeled and not allow_unlabeled:
                errors.append("TARGET_UNLABELED")
            elif unlabeled:
                warnings.append("TARGET_CONTAINS_UNLABELED_ROWS")

        duplicate_rows = int(dataframe.duplicated().sum())
        if duplicate_rows:
            warnings.append("DUPLICATE_ROWS")

        report = {
            "valid": not errors,
            "rows": len(dataframe),
            "columns": len(dataframe.columns),
            "required_features": required_features,
            "missing_columns": missing_columns,
            "missing_feature_values": missing_feature_values,
            "target_present": not target_missing,
            "unlabeled": unlabeled,
            "invalid_targets": invalid_targets,
            "duplicate_rows": duplicate_rows,
            "errors": list(dict.fromkeys(errors)),
            "warnings": list(dict.fromkeys(warnings)),
        }

        self.last_report = report
        return report

    def validate(self, dataframe: pd.DataFrame, **options: Any) -> bool:
        return bool(self.evaluate(dataframe, **options)["valid"])

    def require(self, dataframe: pd.DataFrame, **options: Any) -> pd.DataFrame:
        report = self.evaluate(dataframe, **options)
        if not report["valid"]:
            raise ValueError(
                "Dataset inválido: " + ", ".join(report["errors"])
            )
        return dataframe



dataset_validator = DatasetValidator()
