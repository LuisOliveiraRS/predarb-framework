from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any

import pandas as pd


class DatasetWriter:
    """Salva CSV de forma atômica para evitar arquivos parciais."""

    def __init__(self) -> None:
        self.last_report: dict[str, Any] = {}

    def save(
        self,
        dataframe: pd.DataFrame,
        path: str | Path,
        *,
        overwrite: bool = True,
        encoding: str = "utf-8",
    ) -> Path:
        if not isinstance(dataframe, pd.DataFrame):
            raise TypeError("dataframe deve ser um pandas.DataFrame.")

        destination = Path(path).expanduser().resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and not overwrite:
            raise FileExistsError(destination)

        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{destination.stem}-",
            suffix=".tmp",
            dir=destination.parent,
        )
        os.close(descriptor)
        temporary = Path(temporary_name)

        try:
            dataframe.to_csv(temporary, index=False, encoding=encoding)
            temporary.replace(destination)
        except Exception:
            temporary.unlink(missing_ok=True)
            raise

        self.last_report = {
            "path": str(destination),
            "rows": len(dataframe),
            "columns": len(dataframe.columns),
            "bytes": destination.stat().st_size,
            "overwrite": bool(overwrite),
        }

        return destination



dataset_writer = DatasetWriter()
