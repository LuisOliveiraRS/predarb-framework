def test_integrated_modules_import():
    from app.ai import DatasetBuilder, DatasetReader, Trainer
    from app.backtesting.backtest_runner import BacktestRunner
    from app.backtesting.simulation.order_simulator import OrderSimulator
    from app.market_engine.market_engine import MarketEngine
    from app.market_engine.publisher import market_publisher

    assert DatasetBuilder is not None
    assert DatasetReader is not None
    assert Trainer is not None
    assert BacktestRunner is not None
    assert OrderSimulator is not None
    assert MarketEngine is not None
    assert market_publisher is not None
