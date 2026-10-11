"""Regression tests for TradeSimulator execution semantics."""

import pandas as pd
import pytest

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


@pytest.fixture
def simulator():
    return TradeSimulator()


def simulate(simulator, df, *, direction="LONG", entry_index=0,
             entry_price=None, stop_loss, target, max_holding_bars=4):
    if entry_price is None:
        entry_price = float(df["Open"].iloc[entry_index])
    return simulator.simulate(
        symbol="TEST",
        strategy="TEST",
        direction=direction,
        df=df,
        entry_index=entry_index,
        entry_price=entry_price,
        stop_loss=stop_loss,
        target=target,
        max_holding_bars=max_holding_bars,
    )


def test_long_target_hit(simulator):
    df = make_df(
        [100, 100],
        [101, 106],
        [99, 100],
        [100, 104],
    )

    trade = simulate(simulator, df, stop_loss=95, target=105)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_index == 1
    assert trade.exit_price == 105


def test_long_stoploss_hit(simulator):
    df = make_df(
        [100, 100],
        [101, 103],
        [99, 94],
        [100, 96],
    )

    trade = simulate(simulator, df, stop_loss=95, target=105)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_index == 1
    assert trade.exit_price == 95


def test_short_target_and_stoploss(simulator):
    # Price falls through the short target.
    df = make_df(
        [100, 98],
        [101, 99],
        [99, 94],
        [100, 97],
    )

    short_target = simulate(
        simulator, df,
        direction="SHORT", entry_price=100,
        stop_loss=105, target=95,
    )
    assert short_target.exit_reason == "TARGET"
    assert short_target.exit_price == 95

    # Price rises through the short stop intra-bar.
    df_sl = make_df(
        [100, 103],
        [101, 106],
        [99, 102],
        [100, 104],
    )
    short_stop = simulate(
        simulator, df_sl,
        direction="SHORT", entry_price=100,
        stop_loss=105, target=95,
    )
    assert short_stop.exit_reason == "STOPLOSS"
    assert short_stop.exit_price == 105


def test_timeout_exits_at_last_close(simulator):
    df = make_df(
        [100, 100, 100, 100],
        [101, 102, 102, 102],
        [99, 98, 98, 98],
        [100, 101, 101, 101],
    )

    trade = simulate(simulator, df, stop_loss=80, target=150,
                     max_holding_bars=2)

    assert trade.exit_reason == "TIMEOUT"
    assert trade.exit_index == 2
    assert trade.exit_price == float(df["Close"].iloc[2])


def test_end_of_data(simulator):
    df = make_df(
        [100, 100],
        [101, 102],
        [99, 98],
        [100, 101],
    )

    trade = simulate(simulator, df, stop_loss=80, target=150,
                     max_holding_bars=10)

    assert trade.exit_reason == "END_OF_DATA"
    assert trade.exit_index == len(df) - 1


def test_same_bar_stop_wins_over_target(simulator):
    # Bar 1 touches both stop (low 94) and target (high 106);
    # ambiguity must resolve conservatively to the stop.
    df = make_df(
        [100, 100],
        [101, 106],
        [99, 94],
        [100, 101],
    )

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=1)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_price == 95


def test_gap_through_stop_fills_at_open(simulator):
    # Bar 1 OPENS below the stop: fill must be the open, not the level.
    df = make_df(
        [100, 93],
        [101, 94],
        [99, 92],
        [100, 93.5],
    )

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=2)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_index == 1
    assert trade.exit_price == 93


def test_gap_through_target_fills_at_open(simulator):
    # Bar 1 OPENS above the target: better fill at the open.
    df = make_df(
        [100, 108],
        [101, 109],
        [99, 107],
        [100, 108],
    )

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=2)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_index == 1
    assert trade.exit_price == 108


def test_entry_bar_participates_in_scan(simulator):
    # Stop is hit on the ENTRY bar itself (post-open movement).
    df = make_df(
        [100],
        [101],
        [90],
        [100],
    )

    trade = simulate(simulator, df, stop_loss=95, target=150,
                     max_holding_bars=3)

    assert trade.exit_reason == "STOPLOSS"
    assert trade.exit_index == 0
    assert trade.holding_bars == 0


def test_entry_on_last_bar_allowed(simulator):
    df = make_df(
        [100, 100, 100],
        [101, 102, 101],
        [99, 98, 99],
        [100, 101, 100],
    )

    trade = simulate(simulator, df, entry_index=2,
                     stop_loss=80, target=150, max_holding_bars=5)

    assert trade.exit_reason == "END_OF_DATA"
    assert trade.entry_index == 2
    assert trade.exit_index == 2


def test_invalid_inputs_raise(simulator):
    df = make_df([100], [101], [99], [100])

    with pytest.raises(ValueError):
        simulate(simulator, df, direction="FLAT",
                 stop_loss=95, target=105)

    with pytest.raises(ValueError):
        simulate(simulator, df, entry_index=5, entry_price=100.0,
                 stop_loss=95, target=105)


# ── Fill realism: a resting limit target needs a trade *through* ──────────
# Default model is "trade_through" (5 bps buffer). These pin that a mere
# graze of the target no longer fills it, while a genuine through does.

def test_trade_through_rejects_a_mere_touch(simulator):
    # Bar high == target (105) but never trades through -> no fill.
    df = make_df([100, 100], [101, 105], [99, 100], [100, 104])

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=1)

    assert trade.exit_reason != "TARGET"


def test_trade_through_buffer_blocks_a_graze_above_target(simulator):
    # high 105.04 > target 105 but inside the 5 bps buffer
    # (105 * 1.0005 = 105.0525): still no fill.
    df = make_df([100, 100], [101, 105.04], [99, 100], [100, 104])

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=1)

    assert trade.exit_reason != "TARGET"


def test_trade_through_fills_when_price_clears_the_buffer(simulator):
    df = make_df([100, 100], [101, 106], [99, 100], [100, 104])

    trade = simulate(simulator, df, stop_loss=95, target=105,
                     max_holding_bars=1)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_price == 105


def test_touch_model_is_the_legacy_optimistic_graze_fill():
    sim = TradeSimulator(fill_model="touch")
    df = make_df([100, 100], [101, 105], [99, 100], [100, 104])

    trade = simulate(sim, df, stop_loss=95, target=105,
                     max_holding_bars=1)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_price == 105


def test_short_trade_through_rejects_a_mere_touch(simulator):
    df = make_df([100, 98], [101, 99], [99, 95], [100, 97])

    trade = simulate(simulator, df, direction="SHORT", entry_price=100,
                     stop_loss=105, target=95, max_holding_bars=1)

    assert trade.exit_reason != "TARGET"


def test_short_trade_through_fills_when_price_clears_buffer(simulator):
    df = make_df([100, 98], [101, 99], [99, 94], [100, 97])

    trade = simulate(simulator, df, direction="SHORT", entry_price=100,
                     stop_loss=105, target=95, max_holding_bars=1)

    assert trade.exit_reason == "TARGET"
    assert trade.exit_price == 95


def test_invalid_fill_model_raises():
    with pytest.raises(ValueError):
        TradeSimulator(fill_model="midpoint")
