import pandas as pd

from app.backtesting.backtest_runner import BacktestRunner


def test_backtest_runner_reads_dataset_and_returns_statistics(tmp_path):
    path = tmp_path / "history.csv"
    pd.DataFrame(
        [
            {"created_at": "2026-01-01T00:00:00Z", "profit": 10.0},
            {"created_at": "2026-01-02T00:00:00Z", "profit": -2.0},
            {"created_at": "2026-01-03T00:00:00Z", "profit": 4.0},
        ]
    ).to_csv(path, index=False)

    runner = BacktestRunner()
    result = runner.run(path, initial_capital=10_000)

    assert result["final_equity"] == 10_012.0
    assert result["trades"] == 3
    assert runner.last_report["rows"] == 3
