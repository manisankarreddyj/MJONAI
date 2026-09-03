"""Regression test: signals must fill at the NEXT bar's open, never
at the signal bar's close (look-ahead bias)."""

import numpy as np
import pandas as pd
import pytest

from mjonai.research.backtest.engine import BacktestEngine
from mjonai.research.strategy import Strategy, StrategyResult


class OneSignalStrategy(Strategy):
    """Fires exactly one LONG signal on a known bar."""

    def __init__(self, signal_index: int):
        self.signal_index = signal_index

    @property
    def name(self):
        return "OneSignal"

    @property
    def version(self):
        return "1.0"

    @property
    def timeframe(self):
        return "1d"

    def generate_signal(self, data) -> StrategyResult | None:
        if len(data) - 1 != self.signal_index:
            return None
        return StrategyResult(
            symbol="",
            strategy_id=self.name,
            signal="LONG",
            score=100.0,
            index=len(data) - 1,
        )


def make_df(n=10):
    rng = np.random.default_rng(7)
    close = 100 + np.cumsum(rng.normal(0, 1, n))
    return pd.DataFrame(
        {
            "Open": close + 0.5,
            "High": close + 1.5,
            "Low": close - 1.5,
            "Close": close,
        },
        index=pd.date_range("2024-01-01", periods=n),
    )


def fixed_stop(df, signal_index, entry_price, direction):
    return entry_price * 0.97 if direction == "LONG" else entry_price * 1.03


def fixed_target(entry_price, stop_loss, direction):
    risk = abs(entry_price - stop_loss)
    return entry_price + risk * 2 if direction == "LONG" else entry_price - risk * 2


def test_entry_is_next_bar_open():
    df = make_df()
    signal_index = 3

    engine = BacktestEngine()

    trades = engine.run(
        strategy=OneSignalStrategy(signal_index),
        symbol="TEST",
        df=df,
        signals=[StrategyResult(
            symbol="TEST",
            strategy_id="OneSignal",
            signal="LONG",
            score=100.0,
            index=signal_index,
        )],
        stop_loss_func=fixed_stop,
        target_func=fixed_target,
        max_holding_bars=5,
    )

    assert len(trades) == 1

    trade = trades[0]

    assert trade.entry_index == signal_index + 1
    assert trade.entry_price == float(df["Open"].iloc[signal_index + 1])
    assert trade.entry_price != float(df["Close"].iloc[signal_index])
    # Stop must be anchored to the actual fill price.
    assert trade.stop_loss == pytest.approx(trade.entry_price * 0.97)


def test_signal_on_last_bar_produces_no_trade():
    df = make_df()

    engine = BacktestEngine()

    trades = engine.run(
        strategy=OneSignalStrategy(len(df) - 1),
        symbol="TEST",
        df=df,
        signals=[StrategyResult(
            symbol="TEST",
            strategy_id="OneSignal",
            signal="LONG",
            score=100.0,
            index=len(df) - 1,
        )],
        stop_loss_func=fixed_stop,
        target_func=fixed_target,
        max_holding_bars=5,
    )

    assert trades == []
