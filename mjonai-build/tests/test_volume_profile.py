"""
Unit and Institutional Test Suite for S11 Volume Profile Auction Strategy
(strategy/registry/volume_profile.py)
"""

import numpy as np
import pandas as pd
import pytest

from strategy.registry.volume_profile import VolumeProfileStrategy
from strategy.registry.base import StrategySignalResult


@pytest.fixture
def volume_profile_val_bounce_df():
    """
    Generates an 80-row synthetic DataFrame with a Gaussian volume distribution around POC (~200.0)
    and a clean price rejection bounce off Value Area Low (~195.0) with high RVOL.
    """
    np.random.seed(42)
    n = 80
    close = 200.0 + np.random.normal(0, 3.5, n)
    volume = 30000.0 * np.exp(-((close - 200.0) ** 2) / 30.0) + 5000.0

    # Final 3 bars: Dip to VAL (~195.0) and bounce to 197.0 on high volume
    close[-3] = 197.0
    close[-2] = 194.0
    close[-1] = 197.0
    open_ = close.copy()
    open_[-1] = 194.5
    high = close + 1.5
    low = close - 1.5
    low[-1] = 193.0  # lower shadow rejection at VAL
    volume[-1] = 45000.0

    return pd.DataFrame({
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def test_volume_profile_metadata():
    strategy = VolumeProfileStrategy()
    assert strategy.name == "S11_VolumeProfile"
    assert strategy.version == "1.0"


def test_volume_profile_val_bounce_signal(volume_profile_val_bounce_df):
    strategy = VolumeProfileStrategy()
    signal = strategy.generate_signal(
        df=volume_profile_val_bounce_df,
        symbol="TATASTEEL",
        vix=15.0,
        market_state="BULL",
        mqi_level="HIGH",
    )

    assert signal is not None
    assert isinstance(signal, StrategySignalResult)
    assert signal.is_valid() is True
    assert signal.signal_direction == "LONG"
    assert "poc" in signal.indicator_values
    assert "val" in signal.indicator_values
    assert signal.technical_score >= 70.0
