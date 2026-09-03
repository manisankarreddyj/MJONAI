"""Regression test: the backtester holds one position per symbol —
signals whose entry overlaps an open trade are skipped."""

import pandas as pd

from mjonai.research.backtest.engine import BacktestEngine
from mjonai.research.strategy import StrategyResult


def flat_df(n=12):
    """Flat prices guarantee no stop/target hit -> deterministic
    TIMEOUT exits at exactly `max_holding_bars` after entry."""
    return pd.DataFrame(
        {
            "Open": [100.0] * n,
            "High": [100.5] * n,
            "Low": [99.5] * n,
            "Close": [100.0] * n,
        },
        index=pd.date_range("2024-01-01", periods=n),
    )


def fixed_stop(df, signal_index, entry_price, direction):
    return entry_price * 0.97 if direction == "LONG" else entry_price * 1.03


def fixed_target(entry_price, stop_loss, direction):
    risk = abs(entry_price - stop_loss)
    return entry_price + risk * 2 if direction == "LONG" else entry_price - risk * 2


def signal_at(index):
    return StrategyResult(
        symbol="TEST",
        strategy_id="S",
        signal="LONG",
        score=100.0,
        index=index,
    )


def run(df, signals, max_holding_bars):
    engine = BacktestEngine()
    return engine.run(
        strategy=str("S"),
        symbol="TEST",
        df=df,
        signals=signals,
        stop_loss_func=fixed_stop,
        target_func=fixed_target,
        max_holding_bars=max_holding_bars,
    )


def test_overlapping_signals_are_skipped():
    # Trade 1 enters bar 2 and times out at bar 7.
    # Signal at 4 would enter bar 5 (overlap -> dropped);
    # signal at 8 enters bar 9 (after exit -> taken).
    trades = run(flat_df(), [signal_at(1), signal_at(4), signal_at(8)], 5)

    assert len(trades) == 2
    assert trades[0].entry_index == 2
    assert trades[0].exit_reason == "TIMEOUT"
    assert trades[0].exit_index == 7
    assert trades[1].entry_index == 9
    assert trades[1].entry_index > trades[0].exit_index


def test_back_to_back_trades_do_not_overlap():
    trades = run(
        flat_df(n=20),
        [signal_at(i) for i in range(1, 16)],
        max_holding_bars=3,
    )

    assert trades

    for previous, current in zip(trades, trades[1:]):
        assert current.entry_index > previous.exit_index
