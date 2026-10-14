"""
Unit and Institutional Test Suite for Universal Multi-LLM Bridge & Failover Engine
(agents/llm_bridge.py)
"""

import json
import pytest
from unittest.mock import patch, MagicMock

from mjonai.agents.llm_bridge import (
    RateLimitConfig,
    RateLimitTracker,
    extract_and_validate_json,
    get_deterministic_fallback_consensus,
    get_dynamic_candidate_models,
    query_llm_fast,
    LLMInferenceResult,
    probe_providers,
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


def test_verdict_vocabulary_preserved_per_persona():
    """P0: the shared layer erased Bull SELL→VETO and macro/bear reads→NEUTRAL,
    so SHORTs could never confirm via LLM and the macro LLM path always read
    neutral. A per-persona vocabulary preserves exact tokens verbatim."""
    sell = '{"verdict": "SELL", "confidence": 70}'
    # Legacy default (supervisor-shaped): SELL collapses to VETO — unchanged.
    assert extract_and_validate_json(sell)["verdict"] == "VETO"
    # Bull vocabulary: SELL survives for SHORT confirmation.
    bull_vocab = ("STRONG_BUY", "BUY", "APPROVE", "STRONG_SELL", "SELL",
                  "VETO", "REJECT", "CAUTION", "NEUTRAL")
    assert extract_and_validate_json(sell, allowed_verdicts=bull_vocab)["verdict"] == "SELL"
    assert extract_and_validate_json('{"verdict": "STRONG_SELL"}',
                                     allowed_verdicts=bull_vocab)["verdict"] == "STRONG_SELL"
    # Macro vocabulary: tailwind survives instead of NEUTRAL.
    macro_vocab = ("STRONG_TAILWIND", "MODERATE_SUPPORT", "NEUTRAL", "LIQUIDITY_HEADWIND")
    assert extract_and_validate_json('{"verdict": "STRONG_TAILWIND"}')["verdict"] == "NEUTRAL"
    assert extract_and_validate_json('{"verdict": "STRONG_TAILWIND"}',
                                     allowed_verdicts=macro_vocab)["verdict"] == "STRONG_TAILWIND"
    # Outside-vocab tokens still fail closed to NEUTRAL, never approval.
    assert extract_and_validate_json('{"verdict": "APPROVE"}',
                                     allowed_verdicts=macro_vocab)["verdict"] == "NEUTRAL"


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
    mock_payload = '{"verdict": "APPROVE", "confidence": 92, "reasons": ["GPT-OSS 120B consensus approved"]}'
    with patch("mjonai.agents.llm_bridge._query_groq_http", return_value=mock_payload):
        res = query_llm_fast(prompt="Evaluate signal")
        assert res.success is True
        assert res.vendor_used == "groq"
        assert res.model == "openai/gpt-oss-120b"
        assert res.is_fallback is False
        assert res.parsed_payload["verdict"] == "APPROVE"
        assert res.parsed_payload["confidence"] == 92


# ── RateLimitTracker unit tests ─────────────────────────────────────────────

def test_rate_limiter_allows_within_budget():
    tracker = RateLimitTracker()
    tracker.set_provider_limit("groq", RateLimitConfig(rpm=3, rpd=14400))
    tracker.set_model_limit("groq:openai/gpt-oss-120b", RateLimitConfig(rpm=3, rpd=14400))
    assert tracker.can_request("groq", model_key="groq:openai/gpt-oss-120b") is True
    tracker.record("groq", model_key="groq:openai/gpt-oss-120b")
    tracker.record("groq", model_key="groq:openai/gpt-oss-120b")
    assert tracker.can_request("groq", model_key="groq:openai/gpt-oss-120b") is True


def test_rate_limiter_blocks_when_budget_exhausted():
    tracker = RateLimitTracker()
    tracker.set_provider_limit("groq", RateLimitConfig(rpm=2, rpd=100))
    tracker.set_model_limit("groq:m1", RateLimitConfig(rpm=2, rpd=100))
    tracker.record("groq", model_key="groq:m1")
    tracker.record("groq", model_key="groq:m1")
    assert tracker.can_request("groq", model_key="groq:m1") is False


def test_rate_limiter_provider_and_model_independent():
    """Per-model exhaustion must not block other models within the same provider."""
    tracker = RateLimitTracker()
    tracker.set_provider_limit("groq", RateLimitConfig(rpm=10, rpd=100))
    tracker.set_model_limit("groq:m1", RateLimitConfig(rpm=1, rpd=100))
    tracker.set_model_limit("groq:m2", RateLimitConfig(rpm=1, rpd=100))
    tracker.record("groq", model_key="groq:m1")
    assert tracker.can_request("groq", model_key="groq:m1") is False
    assert tracker.can_request("groq", model_key="groq:m2") is True
    assert tracker.can_request("groq", model_key="groq:m1") is False  # still blocked


def test_rate_limiter_window_rolls_over():
    """After the minute window, budget is restored."""
    import time as _time
    tracker = RateLimitTracker()
    tracker.set_provider_limit("groq", RateLimitConfig(rpm=1, rpd=100))
    tracker.record("groq")
    assert tracker.can_request("groq") is False
    with patch("mjonai.agents.llm_bridge.time.time", return_value=_time.time() + 61.0):
        assert tracker.can_request("groq") is True


# ── Dynamic model discovery tests ───────────────────────────────────────────

def test_dynamic_candidate_models_falls_back_to_registry():
    """Discovery failure must fall back to the static registry list."""
    with patch("mjonai.agents.llm_bridge._list_groq_models", return_value=None):
        models = get_dynamic_candidate_models("groq")
        assert "openai/gpt-oss-120b" in models


def test_dynamic_candidate_models_uses_discovery():
    """Successful discovery must supersede the static list."""
    with patch("mjonai.agents.llm_bridge._list_groq_models", return_value=["openai/gpt-oss-550b", "custom/model-x"]):
        models = get_dynamic_candidate_models("groq")
        assert "openai/gpt-oss-550b" in models
        assert "custom/model-x" in models


def test_probe_providers_never_raises():
    """probe_providers must return a health dict even with total API failure."""
    with patch.dict("os.environ", {}, clear=True):
        health = probe_providers()
        assert isinstance(health, dict)
        for name in ("groq", "gemini", "openrouter"):
            assert name in health
            assert "status" in health[name]
            assert "key_present" in health[name]


def test_probe_providers_ok_on_valid_response():
    """With keys present and a working vendor, status should be OK."""
    probe_payload = '{"verdict":"NEUTRAL","confidence":50}'
    env = {
        "GROQ_API_KEY": "gsk_test",
        "GEMINI_API_KEY": "AIza_test",
        "OPENROUTER_API_KEY": "sk-or-test",
    }
    with patch.dict("os.environ", env, clear=True), \
         patch("mjonai.agents.llm_bridge._query_groq_http", return_value=probe_payload), \
         patch("mjonai.agents.llm_bridge._query_gemini_http", return_value=probe_payload), \
         patch("mjonai.agents.llm_bridge._query_openrouter_http", return_value=probe_payload), \
         patch("mjonai.agents.llm_bridge.get_dynamic_candidate_models", side_effect=lambda p: [p + "-model"]):
        health = probe_providers()
        assert health["groq"]["status"] == "OK"
        assert health["gemini"]["status"] == "OK"
        assert health["openrouter"]["status"] == "OK"
        assert health["groq"]["models_working"]
