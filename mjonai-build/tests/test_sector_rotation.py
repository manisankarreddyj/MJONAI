"""
Unit and Institutional Test Suite for Sector Rotation & Relative Rotation Graphs (RRG)
(intelligence/sector_rotation.py)
"""

import pytest

from intelligence.sector_rotation import (
    calculate_rrg_quadrant,
    get_sector_confidence_multiplier,
    calculate_defensive_vs_cyclical_breadth,
    analyze_sector_rotation,
    SectorRotationResult,
)


def test_calculate_rrg_quadrant_all_four_phases():
    """Verify Julius de Kempenaer's RRG 4-Quadrant phase classification."""
    # 1. LEADING (RS >= 100, Mom >= 100)
    assert calculate_rrg_quadrant(rs_ratio=102.5, rs_momentum=101.8) == "LEADING"

    # 2. WEAKENING (RS >= 100, Mom < 100)
    assert calculate_rrg_quadrant(rs_ratio=103.0, rs_momentum=98.5) == "WEAKENING"

    # 3. LAGGING (RS < 100, Mom < 100)
    assert calculate_rrg_quadrant(rs_ratio=97.0, rs_momentum=96.0) == "LAGGING"

    # 4. IMPROVING (RS < 100, Mom >= 100)
    assert calculate_rrg_quadrant(rs_ratio=96.5, rs_momentum=102.0) == "IMPROVING"


def test_get_sector_confidence_multiplier():
    """Verify conviction scoring multipliers."""
    assert get_sector_confidence_multiplier("LEADING") == 1.15
    assert get_sector_confidence_multiplier("IMPROVING") == 1.10
    assert get_sector_confidence_multiplier("WEAKENING") == 1.00
    assert get_sector_confidence_multiplier("LAGGING") == 0.80


def test_calculate_defensive_vs_cyclical_breadth():
    """Verify market participation breadth between defensives and cyclicals."""
    # 1. Cyclical Dominance (Risk-On)
    risk_on_perf = {
        "AUTO": 2.5,
        "METAL": 3.0,
        "REALTY": 2.0,
        "IT": 0.2,
        "PHARMA": 0.1,
        "FMCG": -0.5,
    }
    res_on = calculate_defensive_vs_cyclical_breadth(risk_on_perf)
    assert res_on["market_breadth"] == "AGGRESSIVE_RISK_ON_CYCLICAL_DOMINANCE"
    assert res_on["spread_pct"] > 0

    # 2. Defensive Dominance (Risk-Off)
    risk_off_perf = {
        "AUTO": -1.5,
        "METAL": -2.0,
        "REALTY": -1.8,
        "IT": 1.5,
        "PHARMA": 2.0,
        "FMCG": 1.2,
    }
    res_off = calculate_defensive_vs_cyclical_breadth(risk_off_perf)
    assert res_off["market_breadth"] == "DEFENSIVE_ROTATION_RISK_OFF"
    assert res_off["spread_pct"] < 0


def test_analyze_sector_rotation_contract_and_rankings():
    """Verify full sector rotation analysis, RRG ranking, and dictionary serialization."""
    perf = {
        "REALTY": 3.2,
        "METAL": 2.1,
        "IT": 1.5,
        "AUTO": 0.8,
        "BANK": 0.5,
        "PHARMA": -0.2,
        "FMCG": -1.1,
    }
    res = analyze_sector_rotation(sector_performance_dict=perf, benchmark_return_pct=0.8)

    assert "leading_sectors" in res
    assert "improving_sectors" in res
    assert "weakening_sectors" in res
    assert "lagging_sectors" in res
    assert res["top_sector_pick"] == "REALTY"
    assert len(res["sector_rankings"]) == len(perf)

    # Verify each ranking item contains RRG fields
    top_rank = res["sector_rankings"][0]
    assert "rs_ratio" in top_rank
    assert "rs_momentum" in top_rank
    assert "rrg_quadrant" in top_rank
    assert "confidence_multiplier" in top_rank
