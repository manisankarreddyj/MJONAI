import pytest
import numpy as np
import pandas as pd

from mjonai.data.derivatives.gex_engine import (
    calculate_gamma_exposure,
    calculate_black_scholes_gamma,
    GammaRegime,
)
from mjonai.data.derivatives.participant_oi import (
    parse_participant_oi_data,
    InstitutionalPositioningZone,
)
from mjonai.data.derivatives.fo_ban_sentry import (
    check_fo_ban_status,
    update_mwpl_utilization,
    BanStatus,
)
from mjonai.strategy.registry.quant_math import (
    calculate_hurst_exponent,
    yang_zhang_volatility,
    kalman_filter_1d,
    amihud_illiquidity_ratio,
    corwin_schultz_spread,
)


def test_black_scholes_gamma_and_gex_engine():
    """Verify Dealer Gamma Exposure and Zero-Gamma calculation."""
    gamma = calculate_black_scholes_gamma(spot=23800.0, strike=23800.0, dte_days=4.0, iv=0.14)
    assert gamma > 0.0, "ATM Gamma must be positive"

    strikes = [23600, 23700, 23800, 23900, 24000]
    call_oi = [15000, 25000, 65000, 95000, 120000]
    put_oi  = [110000, 85000, 55000, 20000, 10000]

    gex_snap = calculate_gamma_exposure(
        underlying="NIFTY",
        spot_price=23820.0,
        strikes=strikes,
        call_oi=call_oi,
        put_oi=put_oi,
        dte_days=4.0,
        default_iv=0.14,
        lot_size=65,
    )

    assert gex_snap.underlying == "NIFTY"
    assert gex_snap.zero_gamma_level is not None
    assert gex_snap.major_call_wall == 24000.0
    assert gex_snap.major_put_wall == 23600.0
    assert isinstance(gex_snap.gamma_regime, GammaRegime)


def test_participant_oi_institutional_positioning():
    """Verify NSE Participant Open Interest and Short-Squeeze detection."""
    snap_trap = parse_participant_oi_data(
        fii_index_long=15000,
        fii_index_short=85000,
    )
    assert snap_trap.positioning_zone == InstitutionalPositioningZone.SHORT_SQUEEZE_TRAP
    assert snap_trap.is_short_squeeze_candidate is True
    assert snap_trap.fii_index_fut_ratio < 0.20

    snap_bull = parse_participant_oi_data(
        fii_index_long=70000,
        fii_index_short=30000,
    )
    assert snap_bull.positioning_zone == InstitutionalPositioningZone.BULLISH_ACCUMULATION
    assert snap_bull.fii_index_fut_ratio == 0.70


def test_fo_ban_and_mwpl_sentry():
    """Verify Market-Wide Position Limit tracking and trade blocking."""
    update_mwpl_utilization("RELIANCE", mwpl_pct=45.0)
    snap_safe = check_fo_ban_status("RELIANCE")
    assert snap_safe.ban_status == BanStatus.SAFE
    assert snap_safe.is_trade_allowed is True

    update_mwpl_utilization("PNB", mwpl_pct=88.5)
    snap_danger = check_fo_ban_status("PNB")
    assert snap_danger.ban_status == BanStatus.DANGER_ZONE
    assert snap_danger.is_trade_allowed is True

    update_mwpl_utilization("IDEA", mwpl_pct=96.2)
    snap_banned = check_fo_ban_status("IDEA")
    assert snap_banned.ban_status == BanStatus.BANNED
    assert snap_banned.is_trade_allowed is False


def test_hurst_exponent_regime_classification():
    """Verify Hurst Exponent distinguishes trending vs mean-reverting series."""
    np.random.seed(42)
    trend_series = np.cumsum(np.random.normal(0.5, 1.0, 300))
    h_trend = calculate_hurst_exponent(trend_series)
    assert h_trend > 0.40, f"Trending series should have high H: {h_trend}"

    ou_series = np.zeros(300)
    for t in range(1, 300):
        ou_series[t] = ou_series[t-1] - 0.5 * ou_series[t-1] + np.random.normal(0, 1)
    h_mr = calculate_hurst_exponent(ou_series + 100.0)
    assert h_mr < 0.55, f"Mean-reverting series should have low H: {h_mr}"


def test_yang_zhang_realized_volatility():
    """Verify Yang-Zhang minimum variance realized volatility."""
    n = 100
    np.random.seed(42)
    base = 1000.0
    closes = base + np.cumsum(np.random.normal(0, 5, n))
    opens = closes + np.random.normal(0, 2, n)
    highs = np.maximum(opens, closes) + np.abs(np.random.normal(0, 3, n))
    lows = np.minimum(opens, closes) - np.abs(np.random.normal(0, 3, n))

    yz_vol = yang_zhang_volatility(opens, highs, lows, closes, timeperiod=20)
    assert len(yz_vol) == n
    assert not np.isnan(yz_vol[-1])
    assert yz_vol[-1] > 0.0


def test_kalman_filter_and_microstructure_estimators():
    """Verify 1D Kalman filter and Amihud illiquidity."""
    n = 60
    np.random.seed(42)
    prices = 24000.0 + np.cumsum(np.random.normal(1.0, 10.0, n))
    volumes = np.random.randint(50000, 200000, n)

    filtered_p, vel = kalman_filter_1d(prices)
    assert len(filtered_p) == n
    assert len(vel) == n
    assert not np.isnan(filtered_p[-1])

    illiq = amihud_illiquidity_ratio(prices, volumes, timeperiod=20)
    assert len(illiq) == n
    assert not np.isnan(illiq[-1])

    highs = prices + 15.0
    lows = prices - 15.0
    cs_spread = corwin_schultz_spread(highs, lows, timeperiod=14)
    assert len(cs_spread) == n
