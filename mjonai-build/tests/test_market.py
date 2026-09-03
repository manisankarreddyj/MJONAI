"""
Unit & Integration Tests for data/market/
Broad Market Sectoral Breadth & 09:15-09:30 AM Opening Volume Sentry (TD-011).
"""

from datetime import datetime, timedelta
from pathlib import Path
import sys
import pytest

# Ensure workspace root is in sys.path
_root_dir = Path(__file__).resolve().parent.parent
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

from core.time_utils import now_ist
from data.market.sector_breadth import _live_sector_prices, SECTOR_TICK_STALENESS_SECONDS
from data.market import (
    SectorIndex,
    SECTOR_TOKEN_MAP,
    SectorPerformance,
    SectorBreadthSnapshot,
    AdvanceDeclineSnapshot,
    calculate_sector_breadth,
    calculate_advance_decline_ratio,
    get_sector_relative_strength,
    update_sector_price,
    clear_sector_prices,
    VolumeRegime,
    OpeningVolumeSnapshot,
    calculate_opening_rvol,
    get_intraday_volume_score,
    is_orb_volume_confirmed,
    register_historical_opening_volume,
    clear_opening_volume_cache,
)


@pytest.fixture(autouse=True)
def reset_market_stores():
    """Ensure clean in-memory market stores between test executions."""
    clear_sector_prices()
    clear_opening_volume_cache()
    yield
    clear_sector_prices()
    clear_opening_volume_cache()


# ── 1. SECTOR BREADTH & PARTICIPATION TESTS ───────────────────────────────────

def test_sector_index_enums_and_tokens():
    """Verify all 12 primary NSE sector indices have valid tokens."""
    assert len(SectorIndex) == 12
    for sec in SectorIndex:
        assert sec in SECTOR_TOKEN_MAP
        assert len(SECTOR_TOKEN_MAP[sec]) > 0


def test_sector_breadth_strong_bull_and_bear():
    """Verify strong bullish (>=60%) and strong bearish (<=40%) sector breadth."""
    # 1. 9/12 (75%) sectors positive -> Strong Bull
    bull_returns = {
        SectorIndex.NIFTY_BANK: 0.015,
        SectorIndex.NIFTY_IT: 0.010,
        SectorIndex.NIFTY_AUTO: 0.008,
        SectorIndex.NIFTY_METAL: 0.020,
        SectorIndex.NIFTY_FIN_SERVICE: 0.012,
        SectorIndex.NIFTY_REALTY: 0.025,
        SectorIndex.NIFTY_ENERGY: 0.005,
        SectorIndex.NIFTY_PSU_BANK: 0.030,
        SectorIndex.NIFTY_PVT_BANK: 0.011,
        SectorIndex.NIFTY_FMCG: -0.002,
        SectorIndex.NIFTY_PHARMA: -0.004,
        SectorIndex.NIFTY_MEDIA: -0.006,
    }
    snap_bull = calculate_sector_breadth(bull_returns)
    assert snap_bull.total_sectors == 12
    assert snap_bull.advancing_count == 9
    assert snap_bull.declining_count == 3
    assert snap_bull.breadth_pct == 0.75
    assert snap_bull.is_strong_bull is True
    assert snap_bull.is_strong_bear is False
    assert snap_bull.top_sector == "NIFTY PSU BANK"
    assert snap_bull.lag_sector == "NIFTY MEDIA"
    assert "Sector Breadth Strong" in snap_bull.provenance_reason

    # 2. 3/12 (25%) sectors positive -> Strong Bear
    bear_returns = {
        SectorIndex.NIFTY_BANK: -0.015,
        SectorIndex.NIFTY_IT: -0.010,
        SectorIndex.NIFTY_AUTO: -0.008,
        SectorIndex.NIFTY_METAL: -0.020,
        SectorIndex.NIFTY_FIN_SERVICE: -0.012,
        SectorIndex.NIFTY_REALTY: -0.025,
        SectorIndex.NIFTY_ENERGY: -0.005,
        SectorIndex.NIFTY_PSU_BANK: -0.030,
        SectorIndex.NIFTY_PVT_BANK: -0.011,
        SectorIndex.NIFTY_FMCG: 0.002,
        SectorIndex.NIFTY_PHARMA: 0.004,
        SectorIndex.NIFTY_MEDIA: 0.006,
    }
    snap_bear = calculate_sector_breadth(bear_returns)
    assert snap_bear.advancing_count == 3
    assert snap_bear.declining_count == 9
    assert snap_bear.breadth_pct == 0.25
    assert snap_bear.is_strong_bull is False
    assert snap_bear.is_strong_bear is True
    assert "Sector Breadth Weak" in snap_bear.provenance_reason


def test_sector_breadth_neutral_and_empty_fallback():
    """Verify neutral breadth and offline fallback handling."""
    # Zero ticks available -> 50% neutral fallback
    snap_empty = calculate_sector_breadth()
    assert snap_empty.total_sectors == 0
    assert snap_empty.breadth_pct == 0.50
    assert snap_empty.is_strong_bull is False
    assert snap_empty.is_strong_bear is False
    assert "Offline Baseline" in snap_empty.provenance_reason


def test_sector_breadth_live_tick_store():
    """Verify live price ingestion via update_sector_price.

    Adapted for the coverage gate: breadth over the live store is now only
    computed when at least 8 of 12 fresh sectors are present; a partial feed
    returns the NEUTRAL insufficient-coverage snapshot instead of computing
    over whatever few ticks are cached."""
    # 1. Full-enough sample (9/12 fresh sectors) -> computed normally
    update_sector_price(SectorIndex.NIFTY_BANK, ltp=51000.0, prev_close=50000.0)   # +2.0%
    update_sector_price(SectorIndex.NIFTY_PVT_BANK, ltp=25300.0, prev_close=25000.0)  # +1.2%
    update_sector_price(SectorIndex.NIFTY_FIN_SERVICE, ltp=25250.0, prev_close=25000.0)  # +1.0%
    update_sector_price(SectorIndex.NIFTY_IT, ltp=38500.0, prev_close=38000.0)     # +1.3%
    update_sector_price(SectorIndex.NIFTY_AUTO, ltp=25400.0, prev_close=25000.0)   # +1.6%
    update_sector_price(SectorIndex.NIFTY_FMCG, ltp=50500.0, prev_close=50000.0)   # +1.0%
    update_sector_price(SectorIndex.NIFTY_METAL, ltp=9700.0, prev_close=10000.0)   # -3.0%
    update_sector_price(SectorIndex.NIFTY_PHARMA, ltp=21600.0, prev_close=22000.0)  # -1.8%
    update_sector_price(SectorIndex.NIFTY_MEDIA, ltp=1970.0, prev_close=2000.0)    # -1.5%

    snap = calculate_sector_breadth()
    assert snap.total_sectors == 9
    assert snap.advancing_count == 6
    assert snap.declining_count == 3
    assert snap.breadth_pct == pytest.approx(6 / 9)
    assert snap.top_sector == "NIFTY BANK"
    assert snap.lag_sector == "NIFTY METAL"

    # 2. Partial feed (only 2 fresh sectors) -> rejected as NEUTRAL
    clear_sector_prices()
    update_sector_price(SectorIndex.NIFTY_BANK, ltp=51000.0, prev_close=50000.0)  # +2.0%
    update_sector_price(SectorIndex.NIFTY_IT, ltp=38000.0, prev_close=38500.0)    # -1.3%

    snap_partial = calculate_sector_breadth()
    assert snap_partial.total_sectors == 0          # sample rejected below coverage gate
    assert snap_partial.breadth_pct == 0.50         # neutral baseline
    assert snap_partial.is_strong_bull is False
    assert snap_partial.is_strong_bear is False     # never bearish on missing data
    assert "Insufficient Coverage" in snap_partial.provenance_reason
    assert snap_partial.sector_details == {}


def test_sector_breadth_stale_ticks_excluded():
    """Live ticks older than SECTOR_TICK_STALENESS_SECONDS must be excluded from breadth."""
    now = now_ist()

    # 9 FRESH sectors: 4 advancing / 5 declining -> 44% green (neutral band)
    fresh_plan = [
        (SectorIndex.NIFTY_BANK, 51200.0, 50000.0),          # +2.4%
        (SectorIndex.NIFTY_IT, 38400.0, 38000.0),            # +1.1%
        (SectorIndex.NIFTY_AUTO, 25500.0, 25000.0),          # +2.0%
        (SectorIndex.NIFTY_FMCG, 50600.0, 50000.0),          # +1.2%
        (SectorIndex.NIFTY_METAL, 9500.0, 10000.0),          # -5.0%
        (SectorIndex.NIFTY_PHARMA, 21500.0, 22000.0),        # -2.3%
        (SectorIndex.NIFTY_REALTY, 970.0, 1000.0),           # -3.0%
        (SectorIndex.NIFTY_ENERGY, 39200.0, 40000.0),        # -2.0%
        (SectorIndex.NIFTY_FIN_SERVICE, 24700.0, 25000.0),   # -1.2%
    ]
    for sec, ltp, prev_close in fresh_plan:
        update_sector_price(sec, ltp=ltp, prev_close=prev_close)

    # 1 STALE sector (-10% dump, timestamped 20 min ago): if it were counted,
    # breadth would drop to 4/10 = 40% and trip the Strong Bear flag.
    stale_ts = now - timedelta(seconds=int(SECTOR_TICK_STALENESS_SECONDS) + 600)
    _live_sector_prices[SectorIndex.NIFTY_MEDIA] = (9000.0, 10000.0, stale_ts)

    snap = calculate_sector_breadth()
    assert snap.total_sectors == 9                       # stale sector excluded
    assert "NIFTY MEDIA" not in snap.sector_details
    assert snap.advancing_count == 4
    assert snap.declining_count == 5
    assert snap.breadth_pct == pytest.approx(4 / 9)
    assert snap.is_strong_bear is False                  # not driven by stale data
    assert snap.is_strong_bull is False

    # All ticks stale -> explicitly NEUTRAL (never bearish)
    clear_sector_prices()
    _live_sector_prices[SectorIndex.NIFTY_BANK] = (45000.0, 50000.0, stale_ts)
    snap_all_stale = calculate_sector_breadth()
    assert snap_all_stale.total_sectors == 0
    assert snap_all_stale.breadth_pct == 0.50
    assert snap_all_stale.is_strong_bull is False
    assert snap_all_stale.is_strong_bear is False
    assert "No Fresh Sector Ticks" in snap_all_stale.provenance_reason


def test_sector_relative_strength_alpha():
    """Verify Sector Alpha relative to Benchmark NIFTY 50."""
    returns = {
        SectorIndex.NIFTY_BANK: 0.020,  # +2.0%
        SectorIndex.NIFTY_IT: -0.005,   # -0.5%
    }
    nifty_chg = 0.010  # +1.0%

    alpha_map = get_sector_relative_strength(nifty_chg, returns)
    assert alpha_map["NIFTY BANK"] == 0.010   # +2.0% - (+1.0%) = +1.0% Alpha
    assert alpha_map["NIFTY IT"] == -0.015    # -0.5% - (+1.0%) = -1.5% Alpha


def test_advance_decline_ratio_and_spread():
    """Verify broad Advance/Decline (A/D) ratio calculations."""
    # Strong Accumulation: 35 Advances, 15 Declines (2.33x)
    ad_bull = calculate_advance_decline_ratio(advances=35, declines=15, unchanged=0)
    assert ad_bull.ad_spread == 20
    assert ad_bull.ad_ratio > 2.0
    assert ad_bull.is_bullish is True
    assert ad_bull.is_bearish is False

    # Heavy Liquidation: 10 Advances, 40 Declines (0.25x)
    ad_bear = calculate_advance_decline_ratio(advances=10, declines=40, unchanged=0)
    assert ad_bear.ad_spread == -30
    assert ad_bear.ad_ratio < 0.50
    assert ad_bear.is_bullish is False
    assert ad_bear.is_bearish is True


# ── 2. OPENING RELATIVE VOLUME (RVOL) TESTS ───────────────────────────────────

def test_opening_volume_regimes_and_rvol():
    """Verify all 4 opening volume regimes."""
    # 1. Ultra Expansion (>= 2.5x)
    snap_ultra = calculate_opening_rvol("NIFTY", opening_volume=5_000_000, avg_20d_opening_volume=2_000_000)
    assert snap_ultra.rvol_ratio == 2.50
    assert snap_ultra.volume_regime == VolumeRegime.ULTRA_EXPANSION_VOLUME
    assert snap_ultra.is_expansion_volume is True
    assert snap_ultra.is_dry_volume is False

    # 2. Expansion (1.5x - 2.5x)
    snap_exp = calculate_opening_rvol("RELIANCE", opening_volume=1_800_000, avg_20d_opening_volume=1_000_000)
    assert snap_exp.rvol_ratio == 1.80
    assert snap_exp.volume_regime == VolumeRegime.EXPANSION_VOLUME
    assert snap_exp.is_expansion_volume is True

    # 3. Normal (0.8x - 1.5x)
    snap_norm = calculate_opening_rvol("TCS", opening_volume=950_000, avg_20d_opening_volume=1_000_000)
    assert snap_norm.rvol_ratio == 0.95
    assert snap_norm.volume_regime == VolumeRegime.NORMAL_VOLUME
    assert snap_norm.is_expansion_volume is False
    assert snap_norm.is_dry_volume is False

    # 4. Dry (< 0.8x)
    snap_dry = calculate_opening_rvol("INFY", opening_volume=450_000, avg_20d_opening_volume=1_000_000)
    assert snap_dry.rvol_ratio == 0.45
    assert snap_dry.volume_regime == VolumeRegime.DRY_VOLUME
    assert snap_dry.is_dry_volume is True


def test_opening_volume_baseline_cache():
    """Verify historical baseline volume registration."""
    register_historical_opening_volume("HDFCBANK", avg_volume_20d=750_000)

    # Calculates RVOL using cached baseline
    snap = calculate_opening_rvol("HDFCBANK", opening_volume=1_500_000)
    assert snap.avg_20d_opening_volume == 750_000
    assert snap.rvol_ratio == 2.0


def test_opening_volume_insufficient_data_is_neutral():
    """Missing/unusable volume inputs yield an explicit insufficient-data NEUTRAL
    result — never a fabricated rvol=1.0 NORMAL_VOLUME (+1 MQI) score."""
    # 1. No baseline registered, no opening volume supplied
    snap_none = calculate_opening_rvol("UNKNOWN_SYM")
    assert snap_none.volume_regime == VolumeRegime.INSUFFICIENT_DATA
    assert snap_none.rvol_ratio == 0.0
    assert snap_none.is_expansion_volume is False
    assert snap_none.is_dry_volume is False
    assert "Insufficient Volume Data" in snap_none.message
    assert get_intraday_volume_score(snap_none.rvol_ratio)[0] == 0

    # 2. Baseline known but current opening volume missing
    snap_no_vol = calculate_opening_rvol("TCS", avg_20d_opening_volume=1_000_000)
    assert snap_no_vol.volume_regime == VolumeRegime.INSUFFICIENT_DATA
    assert snap_no_vol.avg_20d_opening_volume == 1_000_000   # real input preserved
    assert snap_no_vol.rvol_ratio == 0.0
    assert "Insufficient Volume Data" in snap_no_vol.message

    # 3. Opening volume present but no usable baseline anywhere
    snap_no_base = calculate_opening_rvol("RELIANCE", opening_volume=850_000)
    assert snap_no_base.volume_regime == VolumeRegime.INSUFFICIENT_DATA
    assert snap_no_base.opening_volume_15m == 850_000        # real input preserved
    assert snap_no_base.avg_20d_opening_volume == 0.0
    assert snap_no_base.rvol_ratio == 0.0

    # 4. Unusable inputs (negative volume / non-positive registered baseline)
    register_historical_opening_volume("BADBASE", avg_volume_20d=0)
    snap_neg = calculate_opening_rvol("BADBASE", opening_volume=-5.0)
    assert snap_neg.volume_regime == VolumeRegime.INSUFFICIENT_DATA
    assert "Insufficient Volume Data" in snap_neg.message

    # Contrast: with REAL data on both sides, classification still applies.
    snap_real = calculate_opening_rvol("INFY", opening_volume=950_000, avg_20d_opening_volume=1_000_000)
    assert snap_real.volume_regime == VolumeRegime.NORMAL_VOLUME
    assert snap_real.rvol_ratio == 0.95


def test_get_intraday_volume_score_mqi_mapping():
    """Verify direct MQI Factor 6 scoring rules."""
    assert get_intraday_volume_score(1.8)[0] == 2
    assert get_intraday_volume_score(1.0)[0] == 1
    assert get_intraday_volume_score(0.5)[0] == 0
    # Adapted: missing RVOL is now explicit insufficient data (0 points),
    # not a fabricated "+1 Baseline Participation".
    score_none, reason_none = get_intraday_volume_score(None)
    assert score_none == 0
    assert "Insufficient Volume Data" in reason_none


def test_is_orb_volume_confirmed_guard():
    """Verify ORB institutional confirmation guard."""
    assert is_orb_volume_confirmed("NIFTY", opening_volume=300_000, avg_20d_opening_volume=150_000, rvol_threshold=1.5) is True
    assert is_orb_volume_confirmed("NIFTY", opening_volume=120_000, avg_20d_opening_volume=150_000, rvol_threshold=1.5) is False


def test_dataclass_serializations_to_dict():
    """Verify all snapshots serialize to clean dicts."""
    now = datetime.now()
    perf = SectorPerformance(
        sector=SectorIndex.NIFTY_BANK,
        token="99926009",
        ltp=51200.0,
        prev_close=50000.0,
        change_pct=0.024,
        is_advancing=True,
        timestamp=now,
    )
    d_perf = perf.to_dict()
    assert d_perf["sector"] == "NIFTY BANK"
    assert d_perf["is_advancing"] is True

    ad = calculate_advance_decline_ratio(30, 20)
    d_ad = ad.to_dict()
    assert d_ad["advances"] == 30
    assert d_ad["declines"] == 20
    assert d_ad["ad_ratio"] == 1.5
