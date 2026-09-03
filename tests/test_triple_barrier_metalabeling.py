"""
Test Suite: tests/test_triple_barrier_metalabeling.py
Purpose: Verify Marcos López de Prado's Triple Barrier Method for event labeling.
"""

from datetime import datetime, timedelta
import pandas as pd
import numpy as np
import pytest

from mjonai.research.ml.triple_barrier import apply_triple_barrier


def test_triple_barrier_long_profit_and_loss():
    """Verify upper profit target hit vs lower stop loss hit for LONG signals."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")
    
    # 1. Price path that rallies and hits TP
    df_rally = pd.DataFrame({
        "open": [100.0 + i * 2.0 for i in range(30)],
        "high": [102.0 + i * 2.0 for i in range(30)],
        "low": [99.0 + i * 2.0 for i in range(30)],
        "close": [101.0 + i * 2.0 for i in range(30)],
        "volume": [10000] * 30,
    }, index=dates)

    events_rally = pd.DataFrame([
        {"timestamp": dates[2], "direction": "LONG", "entry_price": 105.0, "symbol": "TCS"}
    ])

    labeled_rally = apply_triple_barrier(df_rally, events_rally, pt_multiplier=2.0, sl_multiplier=1.5, max_holding_bars=10)
    assert len(labeled_rally) == 1
    assert labeled_rally[0].exit_barrier == "TAKE_PROFIT"
    assert labeled_rally[0].label == 1
    assert labeled_rally[0].net_return_pct > 0

    # 2. Price path that drops and hits SL
    df_drop = pd.DataFrame({
        "open": [100.0 - i * 2.0 for i in range(30)],
        "high": [101.0 - i * 2.0 for i in range(30)],
        "low": [97.0 - i * 2.0 for i in range(30)],
        "close": [98.0 - i * 2.0 for i in range(30)],
        "volume": [10000] * 30,
    }, index=dates)

    events_drop = pd.DataFrame([
        {"timestamp": dates[2], "direction": "LONG", "entry_price": 95.0, "symbol": "INFY"}
    ])

    labeled_drop = apply_triple_barrier(df_drop, events_drop, pt_multiplier=2.0, sl_multiplier=1.5, max_holding_bars=10)
    assert len(labeled_drop) == 1
    assert labeled_drop[0].exit_barrier == "STOP_LOSS"
    assert labeled_drop[0].label == 0
    assert labeled_drop[0].net_return_pct < 0


def test_triple_barrier_short_direction():
    """Verify upper stop loss hit vs lower profit target hit for SHORT signals."""
    dates = pd.date_range("2024-01-01", periods=30, freq="D")

    # For SHORT, declining price triggers TAKE_PROFIT
    df_drop = pd.DataFrame({
        "open": [100.0 - i * 2.0 for i in range(30)],
        "high": [101.0 - i * 2.0 for i in range(30)],
        "low": [97.0 - i * 2.0 for i in range(30)],
        "close": [98.0 - i * 2.0 for i in range(30)],
        "volume": [10000] * 30,
    }, index=dates)

    events_short = pd.DataFrame([
        {"timestamp": dates[2], "direction": "SHORT", "entry_price": 95.0, "symbol": "RELIANCE"}
    ])

    labeled_short = apply_triple_barrier(df_drop, events_short, pt_multiplier=2.0, sl_multiplier=1.5, max_holding_bars=10)
    assert len(labeled_short) == 1
    assert labeled_short[0].exit_barrier == "TAKE_PROFIT"
    assert labeled_short[0].label == 1
    assert labeled_short[0].net_return_pct > 0
