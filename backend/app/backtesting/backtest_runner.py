from __future__ import annotations

from pathlib import Path
from typing import Any

import pandas as pd

from app.ai.datasets.dataset_reader import DatasetReader, dataset_reader
from app.backtesting.backtest_config import BacktestConfig
from app.backtesting.backtest_engine import BacktestEngine, backtest_engine
from app.strategies.implementations.arbitrage_strategy import arbitrage_strategy


class BacktestRunner:
    """Carrega um dataset histórico e executa o backtest oficial."""

    def __init__(
        self,
        *,
        reader: DatasetReader | None = None,
        engine: BacktestEngine | None = None,
    ) -> None:
        self.reader = reader or dataset_reader
        self.engine = engine or backtest_engine
        self.last_report: dict[str, Any] = {}

    def run(
        self,
        dataset_path: str | Path,
        *,
        initial_capital: float = 10_000.0,
        commission: float = 0.001,
        slippage: float = 0.002,
        latency_ms: int = 120,
    ) -> dict[str, Any]:
        dataframe = self.reader.load(dataset_path)

        if dataframe.empty:
            raise ValueError("O dataset de backtesting está vazio.")

        if "created_at" not in dataframe.columns:
            raise ValueError("O dataset deve possuir a coluna created_at.")

        prepared = dataframe.copy()
        prepared["created_at"] = pd.to_datetime(
            prepared["created_at"],
            utc=True,
            errors="raise",
        )
        prepared = prepared.sort_values("created_at").reset_index(drop=True)

        config = BacktestConfig(
            start=prepared.iloc[0]["created_at"].to_pydatetime(),
            end=prepared.iloc[-1]["created_at"].to_pydatetime(),
            initial_capital=float(initial_capital),
            commission=float(commission),
            slippage=float(slippage),
            latency_ms=int(latency_ms),
        )

        result = self.engine.run(
            prepared,
            arbitrage_strategy,
            config,
        )

        self.last_report = {
            "dataset": str(Path(dataset_path).expanduser().resolve()),
            "rows": len(prepared),
            "start": config.start.isoformat(),
            "end": config.end.isoformat(),
            "initial_capital": config.initial_capital,
            "result": dict(result),
        }
        return result


backtest_runner = BacktestRunner()
