"""
Unit and Institutional Test Suite for Universal Multi-LLM Bridge & Failover Engine
(agents/llm_bridge.py)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from agents.llm_bridge import (
    extract_and_validate_json,
    get_deterministic_fallback_consensus,
    query_llm_fast,
    LLMInferenceResult,
)


def test_extract_and_validate_json_markdown_and_raw():
    """Verify JSON extractor handles raw JSON and markdown wrapped text."""
    # 1. Clean JSON
    raw = '{"verdict": "APPROVE", "confidence": 85, "reasons": ["Strong momentum"]}'
    res = extract_and_validate_json(raw)
    assert res is not None
    assert res["verdict"] == "APPROVE"
    assert res["confidence"] == 85

    # 2. Markdown Wrapped with preamble
    wrapped = """Here is the quantitative analysis:\n```json\n{"verdict": "VETO", "confidence": 120, "reasons": ["RSI overbought"]}\n```\nTrade safely."""
    res_wrap = extract_and_validate_json(wrapped)
    assert res_wrap is not None
    assert res_wrap["verdict"] == "VETO"
    assert res_wrap["confidence"] == 100  # Clamped to max 100


def test_get_deterministic_fallback_consensus_long_and_short():
    """Verify non-blocking algorithmic fallback consensus scoring."""
    # 1. Strong Long setup
    strong_long = {
        "direction": "LONG",
        "rsi": 58.0,
        "volume_ratio": 2.1,
        "sector_multiplier": 1.15,
    }
    macro_context = {"fii_regime": "MEGA_BULLISH"}
    res_long = get_deterministic_fallback_consensus(strong_long, macro_context=macro_context)
    assert res_long["is_deterministic_fallback"] is True
    assert res_long["verdict"] == "APPROVE"
    assert res_long["confidence"] >= 70

    # 2. Weak Overbought Long in Severe Drain -> VETO
    weak_long = {
        "direction": "LONG",
        "rsi": 82.0,
        "volume_ratio": 0.8,
        "sector_multiplier": 0.80,
    }
    res_veto = get_deterministic_fallback_consensus(weak_long, macro_context={"fii_regime": "SEVERE_DRAIN"})
    assert res_veto["verdict"] == "VETO"


def test_query_llm_fast_falls_back_deterministically():
    """Verify query_llm_fast falls back immediately without blocking when keys are absent."""
    with patch.dict("os.environ", {}, clear=True):
        res = query_llm_fast(
            prompt="Analyze this trade",
            signal={"direction": "LONG", "rsi": 55.0, "volume_ratio": 1.5},
        )
        assert isinstance(res, LLMInferenceResult)
        assert res.success is True
        assert res.is_fallback is True
        assert res.vendor_used == "deterministic_fallback"
        assert res.latency_ms < 50.0  # Instant sub-50ms execution
        assert "verdict" in res.parsed_payload


def test_query_llm_fast_groq_stage_one_success():
    """Verify Stage 1 Groq success when API returns valid response."""
    mock_payload = '{"verdict": "APPROVE", "confidence": 92, "reasons": ["Llama 3.3 consensus approved"]}'
    with patch("agents.llm_bridge._query_groq_http", return_value=mock_payload):
        res = query_llm_fast(prompt="Evaluate signal")
        assert res.success is True
        assert res.vendor_used == "groq"
        assert res.model in ("openai/gpt-oss-20b", "llama-3.3-70b-versatile")
        assert res.is_fallback is False
        assert res.parsed_payload["verdict"] == "APPROVE"
        assert res.parsed_payload["confidence"] == 92
