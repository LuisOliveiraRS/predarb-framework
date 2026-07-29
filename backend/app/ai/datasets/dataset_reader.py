from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd


class DatasetReader:
    """Carrega datasets CSV e registra um relatório da leitura."""

    def __init__(self) -> None:
        self.last_report: dict[str, Any] = {}

    def load(
        self,
        path: str | Path,
        *,
        encoding: str = "utf-8",
        **read_csv_options: Any,
    ) -> pd.DataFrame:
        source = Path(path).expanduser().resolve()

        if not source.is_file():
            raise FileNotFoundError(source)

        dataframe = pd.read_csv(
            source,
            encoding=encoding,
            **read_csv_options,
        )

        self.last_report = {
            "path": str(source),
            "rows": len(dataframe),
            "columns": len(dataframe.columns),
            "bytes": source.stat().st_size,
        }

        return dataframe

    read = load



dataset_reader = DatasetReader()
