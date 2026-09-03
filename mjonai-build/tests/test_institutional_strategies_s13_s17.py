import numpy as np
import pandas as pd
import pytest

from strategy.registry.s13_gamma_flip import GammaFlipStrategy
from strategy.registry.s14_pead import PostEarningsDriftStrategy
from strategy.registry.s15_fii_short_squeeze import FIIShortSqueezeStrategy
from strategy.registry.s16_cross_sectional_momentum import CrossSectionalMomentumStrategy
from strategy.registry.s17_order_flow_microprice import OrderFlowMicroPriceStrategy


def make_dummy_df(n=70, base_price=100.0, trend=0.5):
    dates = pd.date_range(end=pd.Timestamp.now(), periods=n, freq="D")
    prices = [base_price + i * trend for i in range(n)]
    df = pd.DataFrame({
        "Open": [p - 0.2 for p in prices],
        "High": [p + 0.8 for p in prices],
        "Low": [p - 0.8 for p in prices],
        "Close": prices,
        "Volume": [100000 + i * 500 for i in range(n)],
    }, index=dates)
    return df


def test_s13_gamma_flip_strategy():
    strat = GammaFlipStrategy()
    assert strat.name == "S13_GammaFlip"
    assert strat.is_active is True

    df = make_dummy_df(50, 22000.0, trend=10.0)
    sig = strat.generate_signal(
        df=df,
        symbol="NIFTY",
        vix=14.0,
        market_state="NEUTRAL",
        mqi_level="HIGH",
        precomputed_indicators={"zero_gamma_level": 22400.0, "total_gex_crores": 150.0},
    )
    if sig:
        assert sig.signal_direction in ("LONG", "SHORT")
        assert sig.entry_price > 0


def test_s14_pead_strategy():
    strat = PostEarningsDriftStrategy()
    assert strat.name == "S14_PostEarningsDrift"
    assert strat.is_active is True

    df = make_dummy_df(60, 1500.0, trend=5.0)
    df.loc[df.index[-1], "Volume"] = 1000000
    df.loc[df.index[-1], "Close"] = 2000.0
    sig = strat.generate_signal(
        df=df,
        symbol="INFY",
        vix=13.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    if sig:
        assert sig.signal_direction == "LONG"
        assert sig.technical_score >= 75


def test_s15_fii_short_squeeze_strategy():
    strat = FIIShortSqueezeStrategy()
    assert strat.name == "S15_FIIShortSqueeze"
    assert strat.is_active is True

    df = make_dummy_df(30, 24000.0, trend=15.0)
    sig = strat.generate_signal(
        df=df,
        symbol="NIFTY",
        vix=15.0,
        market_state="BEAR",
        mqi_level="HIGH",
        precomputed_indicators={"fii_index_fut_ratio": 0.12},
    )
    if sig:
        assert sig.signal_direction == "LONG"
        assert "FII Short Squeeze" in sig.reasons[0]


def test_s16_cross_sectional_momentum_strategy():
    strat = CrossSectionalMomentumStrategy()
    assert strat.name == "S16_CrossSectionalMomentum"
    assert strat.is_active is True

    df = make_dummy_df(70, 500.0, trend=2.0)
    sig = strat.generate_signal(
        df=df,
        symbol="TATAMOTORS",
        vix=14.0,
        market_state="BULL",
        mqi_level="HIGH",
    )
    if sig:
        assert sig.signal_direction == "LONG"


def test_s17_order_flow_microprice_strategy():
    strat = OrderFlowMicroPriceStrategy()
    assert strat.name == "S17_OrderFlowMicroPrice"
    assert strat.is_active is True

    df = make_dummy_df(20, 2500.0, trend=1.0)
    sig = strat.generate_signal(
        df=df,
        symbol="RELIANCE",
        vix=13.0,
        market_state="NEUTRAL",
        mqi_level="HIGH",
        precomputed_indicators={
            "best_bid": 2500.0,
            "best_ask": 2500.5,
            "bid_qty": 90000,
            "ask_qty": 20000,
        },
    )
    if sig:
        assert sig.signal_direction == "LONG"
        assert sig.indicator_values["micro_price"] > 0
