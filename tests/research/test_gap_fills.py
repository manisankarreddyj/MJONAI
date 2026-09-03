"""Regression tests: bars that OPEN beyond a stop/target must fill
at the open (gap semantics), not at the theoretical level."""

import pandas as pd

from mjonai.research.backtest.trade_simulator import TradeSimulator


def make_df(opens, highs, lows, closes):
    return pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
        },
        index=pd.date_range("2025-01-01", periods=len(opens)),
    )


def run(df, **kwargs):
    simulator = TradeSimulator()
    defaults = dict(
        symbol="TEST",
        strategy="TEST",
        direction="LONG",
        df=df,
        entry_index=0,
        entry_price=100.0,
        stop_loss=95.0,
        target=105.0,
        max_holding_bars=5,
    )
    defaults.update(kwargs)
    return simulator.simulate(**defaults)


def test_long_gap_down_through_stop():
    df = make_df([100, 90], [101, 91], [99, 89], [100, 90])

    trade = run(df)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_price == 90.0


def test_long_gap_up_through_target():
    df = make_df([100, 112], [102, 113], [99, 111], [100, 112])

    trade = run(df)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_price == 112.0


def test_short_gap_up_through_stop():
    df = make_df([100, 115], [101, 116], [99, 114], [100, 115])

    trade = run(df, direction="SHORT", stop_loss=105, target=95)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_price == 115.0


def test_short_gap_down_through_target():
    df = make_df([100, 88], [101, 89], [99, 87], [100, 88])

    trade = run(df, direction="SHORT", stop_loss=105, target=95)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_price == 88.0


def test_gap_on_later_bar_not_just_next():
    # Bar 1 is quiet; bar 2 gaps through the stop.
    df = make_df([100, 100, 92], [101, 101, 93], [99, 98, 91], [100, 100, 92])

    trade = run(df)

    assert trade.exit_index == 2
    assert trade.exit_price == 92.0
