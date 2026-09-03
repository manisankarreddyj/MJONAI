"""
G4 data & universe truth regression tests (2026-08-24):
  - H1: universe loader fails LOUDLY instead of silently substituting Nifty 50
  - H2: scrip-master fast path anchors inside mjonai-build and reads the real
        instrument_master_cache.json
  - H6: interior cache gaps are detected (daily cadence), intraday exempt
  - H7: performance metrics share the ledger's INITIAL_CAPITAL single source
  - N2/H8: trade_risk prices through canonical execution/tax.py + 5bps/side
"""

import inspect
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from mjonai.research import universe_loader
from mjonai.research.universe_loader import load_universe_symbols, UniverseTier
from mjonai.research.data.market_data import MarketDataService
from mjonai.analytics.performance import PerformanceAnalyzer
from mjonai.research.backtest.engine import BacktestEngine, INITIAL_CAPITAL
from mjonai.risk.trade_risk import calculate_costs
from mjonai.execution.tax import calculate_all_in_friction


# ── H1: universe truth ────────────────────────────────────────────────────────

def test_nifty500_missing_csv_raises_instead_of_silent_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(
        universe_loader, "NIFTY500_CSV_PATH", str(tmp_path / "missing.csv")
    )
    with pytest.raises(FileNotFoundError):
        load_universe_symbols(tier=UniverseTier.NIFTY_500)


def test_unknown_tier_raises():
    with pytest.raises(ValueError):
        load_universe_symbols(tier="TOTALLY_MADE_UP_TIER")


def test_known_sector_tier_still_works():
    symbols = load_universe_symbols(tier=UniverseTier.NIFTY_IT, max_count=5)
    assert len(symbols) == 5 and all(s == s.upper() for s in symbols)


# ── H2: scrip master fast path ────────────────────────────────────────────────

def test_fast_path_anchors_inside_build_root():
    import os
    from mjonai.data.angelone.scrip_master import LOCAL_TOKENS_CSV, _BUILD_ROOT

    assert LOCAL_TOKENS_CSV.startswith(str(_BUILD_ROOT))
    # The old bug joined D:/mjonai-build/... at the FILESYSTEM root.
    drive, _ = os.path.splitdrive(LOCAL_TOKENS_CSV)
    phantom_root = (drive + "\\mjonai-build").lower()
    assert not LOCAL_TOKENS_CSV.lower().startswith(phantom_root)


def test_master_cache_json_loads_instruments():
    from mjonai.data.angelone.scrip_master import AngelInstrumentProvider, INSTRUMENT_MASTER_CACHE_JSON
    import os

    if not os.path.exists(INSTRUMENT_MASTER_CACHE_JSON):
        pytest.skip("instrument_master_cache.json not synced on this machine")
    instruments = AngelInstrumentProvider().download()
    assert len(instruments) > 100
    sample = instruments[0]
    assert sample.token and sample.symbol and sample.yahoo_symbol.endswith(".NS")


# ── H6: interior cache gap detection ──────────────────────────────────────────

def _candles(spacings_days, start=datetime(2024, 1, 1)):
    out = []
    t = start
    for d in spacings_days:
        out.append(SimpleNamespace(timestamp=t))
        t = t + timedelta(days=d)
    return out


def test_interior_gap_flags_daily_hole():
    svc = MarketDataService()
    # Daily cadence (1-3 day steps incl. weekends) with a ~4-month hole.
    series = _candles([1, 1, 2, 1, 1, 120, 1, 2, 1])
    assert svc._has_suspicious_interior_gap(series) is True


def test_continuous_daily_series_passes():
    svc = MarketDataService()
    # Median daily spacing ~1-2 days; largest legit holiday gap stays well
    # under the 8x threshold.
    series = _candles([1, 1, 2, 1, 3, 1, 1, 2])
    assert svc._has_suspicious_interior_gap(series) is False


def test_intraday_cadence_exempt_from_gap_rule():
    svc = MarketDataService()
    # 5-minute spacing with an overnight-style 16-hour jump — legitimate.
    base = datetime(2024, 1, 2, 9, 15)
    stamps, t = [], base
    for _ in range(60):
        stamps.append(SimpleNamespace(timestamp=t))
        t += timedelta(minutes=5)
        if t.hour >= 15:
            t = t.replace(hour=9, minute=15, second=0) + timedelta(days=1)
    assert svc._has_suspicious_interior_gap(stamps) is False


# ── H7: capital denominator single source ────────────────────────────────────

def test_performance_default_matches_ledger_capital():
    sig = inspect.signature(PerformanceAnalyzer.analyze)
    default = sig.parameters["initial_capital"].default
    assert default == INITIAL_CAPITAL == 1_000_000
    assert BacktestEngine().initial_capital == INITIAL_CAPITAL


# ── N2/H8: one friction engine ────────────────────────────────────────────────

def test_calculate_costs_equals_canonical_plus_slippage():
    entry, qty = 2500.0, 10
    canon = calculate_all_in_friction(buy_price=entry, sell_price=entry, quantity=qty)
    costs = calculate_costs(entry, qty)
    expected_slip = round(entry * qty * 0.0005 * 2, 2)
    assert costs["total"] == round(canon["total_friction"] + expected_slip, 2)
    assert costs["brokerage"] == canon["brokerage"]


def test_intraday_pays_less_than_delivery():
    delivery = calculate_costs(2500.0, 10, product_type="DELIVERY")
    intraday = calculate_costs(2500.0, 10, product_type="INTRADAY")
    assert intraday["stt"] < delivery["stt"]
    assert intraday["total"] < delivery["total"]


def test_marginal_rr_geometry_now_correctly_rejected():
    """N2 behavioral consequence: this fixture was APPROVED by the old lenient
    private cost model; under honest all-in friction (buy-side STT, DP charges)
    its true net R:R falls below the 2.0 gate and must be refused."""
    from mjonai.risk.trade_risk import evaluate_trade_risk_levels

    res = evaluate_trade_risk_levels(
        entry=1000.0,
        atr=15.0,
        confidence=85.0,
        vix=14.0,
        trade_type="SWING",
        signal_direction="LONG",
        system_mode="LIVE",
    )
    assert res.is_approved is False
    assert 0 < res.real_rr < 2.0
