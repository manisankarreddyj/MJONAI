import numpy as np
import pytest
from mjonai.data.microstructure.micro_price import (
    calculate_micro_price_and_impact,
)
from mjonai.strategy.registry.quant_math import (
    fractional_differentiation,
    realized_semivariance,
)
from mjonai.analytics.statistical_validation import deflated_sharpe_pvalue


def test_stoikov_micro_price_and_kyles_lambda():
    """Verify Stoikov (2018) order book micro-price and Kyle's Lambda price impact."""
    # Case 1: Heavy bid pressure (large bid qty, small ask qty -> micro-price jumps toward ask)
    snap_buy = calculate_micro_price_and_impact(
        symbol="RELIANCE",
        best_bid=1300.0,
        best_ask=1301.0,
        bid_qty=80000,
        ask_qty=20000,
        recent_price_change=0.80,
        recent_traded_volume=50000,
    )
    assert snap_buy.mid_price == 1300.50
    assert snap_buy.micro_price == 1300.80  # 1300 * 0.2 + 1301 * 0.8
    assert snap_buy.is_buying_pressure is True
    assert snap_buy.order_book_imbalance == 0.60
    assert snap_buy.kyles_lambda > 0.0

    # Case 2: Heavy ask dumping (large ask qty, small bid qty -> micro-price drops toward bid)
    snap_sell = calculate_micro_price_and_impact(
        symbol="TCS",
        best_bid=3500.0,
        best_ask=3502.0,
        bid_qty=10000,
        ask_qty=90000,
    )
    assert snap_sell.mid_price == 3501.0
    assert snap_sell.micro_price == 3500.20
    assert snap_sell.is_selling_pressure is True


def test_marcos_lopez_de_prado_fractional_differentiation():
    """Verify Fractional Differentiation memory retention and shape."""
    prices = np.array([100.0, 102.0, 101.5, 104.0, 103.5, 106.0, 108.0, 107.0, 110.0, 112.0, 111.0, 115.0, 114.0, 118.0, 120.0])
    frac_diff = fractional_differentiation(prices, d=0.40)
    assert len(frac_diff) == len(prices)
    # Non-NaN output on valid tail
    assert not np.isnan(frac_diff[-1])


def test_realized_semivariance_upside_vs_downside():
    """Verify Good vs Bad Volatility decomposition."""
    returns = np.array([0.02, -0.015, 0.03, -0.04, 0.01, -0.005, 0.025])
    tot_vol, rs_plus, rs_minus = realized_semivariance(returns)
    assert tot_vol > 0
    assert rs_plus > 0
    assert rs_minus > 0
    # Mathematical invariant: tot_vol^2 == rs_plus^2 + rs_minus^2
    assert np.isclose(tot_vol**2, rs_plus**2 + rs_minus**2)


def test_deflated_sharpe_pvalue_statistical_significance():
    """Verify Deflated Sharpe Ratio (DSR) under multiple testing."""
    # High Sharpe (2.8) over 500 samples across 10 trials -> High statistical alpha (DSR p-value > 0.95)
    dsr_high = deflated_sharpe_pvalue(
        sharpe_ratio=2.8,
        num_trials=10,
        sample_length=500,
    )
    assert dsr_high >= 0.95

    # Marginal Sharpe (0.6) after testing 500 strategies -> Spurious false discovery (DSR p-value < 0.50)
    dsr_overfit = deflated_sharpe_pvalue(
        sharpe_ratio=0.6,
        num_trials=500,
        sample_length=100,
    )
    assert dsr_overfit < 0.50

