"""
H3 confidence-honesty regression tests (2026-08-25):
  - missing factors are EXCLUDED (None in breakdown), never fabricated 60-75
  - weights renormalize over available factors only
  - minimum-evidence gate rejects setups without enough REAL corroboration
  - RVOL ratio -> score mapping is bounded and None-preserving
"""

import pytest

from strategy.config import (
    CONFIDENCE_FACTOR_WEIGHTS,
    MIN_EVIDENCE_WEIGHT,
    TECHNICAL_WEIGHT,
    calculate_confidence,
    evaluate_confidence_score,
)
from strategy.pipeline import _rvol_ratio_to_score

AUX_WEIGHT = dict(CONFIDENCE_FACTOR_WEIGHTS)


def test_technical_only_mode_aware_evidence_floor():
    """The old engine approved this everywhere by fabricating nine factors.
    Now: LIVE/PAPER refuse (floor 0.40), RESEARCH may explore (floor 0.20)."""
    live = evaluate_confidence_score(technical=90.0, system_mode="LIVE")
    assert live.is_approved is False
    assert "Insufficient evidence" in live.rejection_reason
    assert live.factors_available == 0
    assert live.evidence_weight_available == pytest.approx(TECHNICAL_WEIGHT)

    research = evaluate_confidence_score(technical=90.0, system_mode="RESEARCH")
    assert research.is_approved is True
    assert research.factors_available == 1
    # Renormalized: technical alone ⇒ confidence == technical score.
    assert research.confidence == pytest.approx(90.0)


def test_missing_factors_are_none_not_defaults():
    res = evaluate_confidence_score(
        technical=85.0, rvol=100.0, mqi_score=80.0, system_mode="RESEARCH"
    )
    assert res.is_approved is True
    for absent in ("mtf", "relative_strength", "sector_breadth",
                   "derivative_oi", "pattern_expectancy", "real_rr",
                   "event_clearance"):
        assert res.breakdown[absent] is None, f"{absent} must not be fabricated"
    assert res.factors_available == 3


def test_weights_renormalize_over_available_only():
    """technical=.20 + rvol=.10 + mqi=.10 → conf = (85*.2+100*.1+80*.1)/.40."""
    res = evaluate_confidence_score(
        technical=85.0, rvol=100.0, mqi_score=80.0, system_mode="RESEARCH"
    )
    expected = round((85.0 * 0.20 + 100.0 * 0.10 + 80.0 * 0.10) / 0.40, 1)
    assert res.confidence == expected
    assert res.evidence_weight_available == 0.4


def test_full_matrix_matches_original_semantics():
    """With ALL factors present the old and new formulas agree exactly."""
    values = dict(technical=85.0, mtf=90.0, relative_strength=85.0, rvol=80.0,
                  sector_breadth=80.0, mqi_score=75.0, derivative_oi=70.0,
                  pattern_expectancy=75.0, real_rr=80.0, event_clearance=100.0)
    res = evaluate_confidence_score(**values, system_mode="LIVE")
    manual = (
        85.0 * 0.20 + 90.0 * 0.15 + 85.0 * 0.15 + 80.0 * 0.10 + 80.0 * 0.10 +
        75.0 * 0.10 + 70.0 * 0.05 + 75.0 * 0.05 + 80.0 * 0.05 + 100.0 * 0.05
    )
    assert res.confidence == pytest.approx(round(manual, 1))
    assert res.is_approved is True


def test_low_technical_still_rejected_first():
    res = evaluate_confidence_score(technical=55.0, rvol=90.0, system_mode="RESEARCH")
    assert res.is_approved is False
    assert "below minimum 60.0" in res.rejection_reason


def test_mode_thresholds_unchanged():
    mid = evaluate_confidence_score(
        technical=70.0, rvol=100.0, mqi_score=70.0, system_mode="RESEARCH"
    )
    live = evaluate_confidence_score(
        technical=70.0, rvol=100.0, mqi_score=70.0, system_mode="LIVE"
    )
    # Same honest confidence (~70); RESEARCH accepts >=50, LIVE demands >=65.
    assert mid.is_approved is True
    assert live.is_approved is (live.confidence >= 65)


def test_rvol_ratio_mapping_bounds_and_none():
    assert _rvol_ratio_to_score(None) is None
    assert _rvol_ratio_to_score(float("nan")) is None
    assert _rvol_ratio_to_score(0.0) is None
    assert _rvol_ratio_to_score(2.0) == 100.0      # 2x caps at full score
    assert _rvol_ratio_to_score(0.5) == 0.0        # half volume floors it
    assert _rvol_ratio_to_score(1.35) == pytest.approx(56.7)


def test_weight_matrix_sums_to_one():
    total = TECHNICAL_WEIGHT + sum(w for _, w in CONFIDENCE_FACTOR_WEIGHTS)
    assert total == pytest.approx(1.0)


# ── pattern-memory factor wiring ──────────────────────────────────────────────

def test_pattern_expectancy_score_mapping(monkeypatch):
    """H3 follow-up: real pattern-memory evidence.
    no record -> None | quarantined -> 0.0 | <3 occurrences -> None |
    real memory -> bounded Laplace win-rate score."""
    from strategy import pipeline as pl

    sr = {"strategy_id": "S01_MomentumRSI", "sl_method": "ATR",
          "candle_pattern": "NONE", "market_state": "BULL"}
    call = lambda **kw: pl._pattern_expectancy_score(
        strategy_result=sr, symbol="TCS", market_state="BULL",
        vix=14.0, system_mode="RESEARCH"
    )

    monkeypatch.setattr("db.patterns.get_pattern", lambda **kw: None)
    assert call() is None

    monkeypatch.setattr(
        "db.patterns.get_pattern",
        lambda **kw: {"is_quarantined": True, "occurrences": 9,
                      "laplace_win_rate_pct": 40.0},
    )
    assert call() == 0.0

    monkeypatch.setattr(
        "db.patterns.get_pattern",
        lambda **kw: {"is_quarantined": False, "occurrences": 2,
                      "laplace_win_rate_pct": 90.0},
    )
    assert call() is None

    monkeypatch.setattr(
        "db.patterns.get_pattern",
        lambda **kw: {"is_quarantined": False, "occurrences": 12,
                      "laplace_win_rate_pct": 66.66},
    )
    assert call() == pytest.approx(66.7)


def test_pattern_expectancy_db_failure_is_none(monkeypatch):
    from strategy import pipeline as pl

    def boom(**kwargs):
        raise RuntimeError("db down")

    monkeypatch.setattr("db.patterns.get_pattern", boom)
    assert pl._pattern_expectancy_score(
        strategy_result={"strategy_id": "S01"}, symbol="X",
        market_state="BULL", vix=14.0, system_mode="RESEARCH"
    ) is None


# ── sector-breadth bridge ─────────────────────────────────────────────────────

def test_sector_breadth_score_symbol_bridge():
    from strategy.pipeline import _sector_breadth_score

    breadth = {"BANKING": 0.6667, "IT": 0.5}
    assert _sector_breadth_score(breadth, "HDFCBANK") == 66.7   # BANKING member
    assert _sector_breadth_score(breadth, "TCS") == 50.0        # IT member
    assert _sector_breadth_score(breadth, "UNKNOWN_SYM") is None  # no sector
    assert _sector_breadth_score(breadth, "HDFCBANK") is not None
    assert _sector_breadth_score(None, "HDFCBANK") is None      # no map
    assert _sector_breadth_score({"ENERGY": 0.4}, "HDFCBANK") is None  # sector absent


def test_scanner_sector_ratios_grouping():
    import pandas as pd
    from strategy.signal_scanner import _compute_sector_advancing_ratios

    def df_pair(prev, last):
        return pd.DataFrame({"Close": [prev, last]})

    setups = [
        (None, {"symbol": "HDFCBANK"}, df_pair(100.0, 110.0)),  # BANKING up
        (None, {"symbol": "SBIN"}, df_pair(100.0, 95.0)),       # BANKING down
        (None, {"symbol": "ICICIBANK"}, df_pair(100.0, 105.0)), # BANKING up
        (None, {"symbol": "TCS"}, df_pair(200.0, 210.0)),       # IT up (2 members only)
        (None, {"symbol": "INFY"}, df_pair(200.0, 205.0)),      # IT up
    ]
    ratios = _compute_sector_advancing_ratios(setups)

    assert ratios["BANKING"] == pytest.approx(2 / 3)
    assert "IT" not in ratios          # below min_members -> no fabricated score

    # NaN closes are excluded, not counted.
    setups_nan = setups + [(None, {"symbol": "KOTAKBANK"}, df_pair(float("nan"), 100.0))]
    ratios2 = _compute_sector_advancing_ratios(setups_nan)
    assert ratios2["BANKING"] == pytest.approx(2 / 3)
