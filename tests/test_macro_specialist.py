"""
Unit tests for agents/macro_specialist.py (Macro & Institutional Flow Specialist Agent).
Verifies deterministic fallback, sector RRG conviction mapping, FII flow regimes,
and mock LLM inference.
"""

from unittest.mock import MagicMock, patch
import pytest

from mjonai.agents.macro_specialist import (
    analyse_macro_flow,
    MacroSpecialistResult,
    _get_deterministic_macro_fallback,
)
from mjonai.agents.llm_bridge import LLMInferenceResult


def test_deterministic_macro_fallback_strong_tailwind():
    ctx = {
        "fii_net_cr": 1200.0,
        "sector_rrg": "LEADING",
        "fii_regime": "HEAVY_BUYING",
    }
    res = _get_deterministic_macro_fallback(ctx)
    assert res["verdict"] == "STRONG_TAILWIND"
    assert res["conviction_score"] >= 80
    assert "Leading RRG" in res["key_drivers"][1]


def test_deterministic_macro_fallback_liquidity_headwind():
    ctx = {
        "fii_net_cr": -1500.0,
        "sector_rrg": "LAGGING",
        "fii_regime": "SEVERE_DRAIN",
    }
    res = _get_deterministic_macro_fallback(ctx)
    assert res["verdict"] == "LIQUIDITY_HEADWIND"
    assert res["conviction_score"] <= 40


def test_analyse_macro_flow_with_mocked_llm():
    mock_llm_res = LLMInferenceResult(
        success=True,
        vendor_used="groq",
        model="llama-3.3-70b-versatile",
        latency_ms=140.0,
        is_fallback=False,
        parsed_payload={
            "verdict": "STRONG_TAILWIND",
            "conviction_score": 85,
            "sector_alignment": "LEADING",
            "key_drivers": ["FII net buying > ₹1000 Cr", "Auto sector leading RRG cycle"],
        },
    )

    signal = {"symbol": "M&M", "direction": "LONG"}
    ctx = {"fii_net_cr": 1050.0, "sector_rrg": "LEADING", "vix": 14.5}

    with patch("mjonai.agents.macro_specialist.query_llm_fast", return_value=mock_llm_res):
        res = analyse_macro_flow(signal, macro_context=ctx)
        assert res["verdict"] == "STRONG_TAILWIND"
        assert res["conviction_score"] == 85
        assert res["sector_alignment"] == "LEADING"
        assert res["model_used"] == "llama-3.3-70b-versatile"
