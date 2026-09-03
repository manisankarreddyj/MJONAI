"""End-to-end backtest pipeline test with a deterministic strategy."""

import numpy as np
import pandas as pd

from research.backtest.engine import BacktestEngine
from research.runner import StrategyRunner
from research.testing.dummy import DummyStrategy


def make_df(n=500, seed=42):
    rng = np.random.default_rng(seed)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "Open": close + 0.5,
            "High": close + rng.random(n) * 2 + 0.5,
            "Low": close - rng.random(n) * 2 - 0.5,
            "Close": close,
            "Volume": rng.integers(1000, 5000, n).astype(float),
        },
        index=pd.date_range("2024-01-01", periods=n),
    )


def stop_loss_func(df, signal_index, entry_price, direction):
    return entry_price * 0.97 if direction == "LONG" else entry_price * 1.03


def target_func(entry_price, stop_loss, direction):
    risk = abs(entry_price - stop_loss)
    return entry_price + risk * 2 if direction == "LONG" else entry_price - risk * 2


def test_pipeline_runs_and_entries_are_next_bar_opens():
    df = make_df()

    strategy = DummyStrategy()

    signals = StrategyRunner(strategy).run(symbol="TEST", data=df)
    assert signals, "DummyStrategy should produce signals on this data"

    engine = BacktestEngine()

    trades = engine.run(
        strategy=strategy,
        symbol="TEST",
        df=df,
        signals=signals,
        stop_loss_func=stop_loss_func,
        target_func=target_func,
        max_holding_bars=20,
    )

    assert trades, "expected at least one completed trade"

    signal_indices = {signal.index for signal in signals}

    for trade in trades:
        # Every fill is one bar after its signal, at that bar's open.
        assert trade.entry_index - 1 in signal_indices
        assert trade.entry_price == float(df["Open"].iloc[trade.entry_index])

    # Trades are affordable positions with real costs applied.
    for trade in trades:
        assert trade.quantity >= 1
        assert trade.transaction_cost.total > 0


def test_engine_resets_capital_between_runs():
    df = make_df()

    strategy = DummyStrategy()

    signals = StrategyRunner(strategy).run(symbol="TEST", data=df)

    engine = BacktestEngine()

    kwargs = dict(
        strategy=strategy,
        symbol="TEST",
        df=df,
        signals=signals,
        stop_loss_func=stop_loss_func,
        target_func=target_func,
        max_holding_bars=20,
    )

    first = engine.run(**kwargs)
    second = engine.run(**kwargs)

    assert len(first) == len(second)
    assert [t.net_pnl for t in first] == [t.net_pnl for t in second]
