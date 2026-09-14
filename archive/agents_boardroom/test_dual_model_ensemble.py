import pytest
from mjonai.agents.dual_model_ensemble import (
    query_dual_model_ensemble,
    DualModelResponse,
)


def test_dual_model_ensemble_agreement_synthesis(monkeypatch):
    """Verify consensus when both Groq and Gemini agree."""
    def mock_groq(prompt, **kwargs):
        return '{"verdict": "APPROVE", "confidence": 80, "key_reasons": ["20-bar breakout"]}'

    def mock_gemini(prompt, **kwargs):
        return '{"verdict": "APPROVE", "confidence": 70, "key_reasons": ["Volume expansion"]}'

    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_groq_http", mock_groq)
    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_gemini_http", mock_gemini)

    res = query_dual_model_ensemble("Evaluate RELIANCE")
    assert res.verdict == "APPROVE"
    assert res.blended_confidence == 75  # (80 + 70) / 2
    assert res.is_cross_model_agreement is True
    assert res.discrepancy_detected is False
    assert len(res.combined_reasons) == 2


def test_dual_model_ensemble_defensive_disagreement(monkeypatch):
    """Verify defensive stance when Groq approves but Gemini flags VETO."""
    def mock_groq(prompt, **kwargs):
        return '{"verdict": "APPROVE", "confidence": 80, "key_reasons": ["Momentum surge"]}'

    def mock_gemini(prompt, **kwargs):
        return '{"verdict": "VETO", "confidence": 85, "key_reasons": ["Severe FII distribution"], "red_flags": ["FII dump"]}'

    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_groq_http", mock_groq)
    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_gemini_http", mock_gemini)

    res = query_dual_model_ensemble("Evaluate RELIANCE")
    assert res.verdict == "VETO"  # Defensive veto adopted
    assert res.is_cross_model_agreement is False
    assert res.discrepancy_detected is True
    assert "FII dump" in res.combined_red_flags


def test_dual_model_ensemble_single_model_fallback(monkeypatch):
    """Verify graceful handling when one provider is offline."""
    def mock_groq(prompt, **kwargs):
        return None  # Groq offline

    def mock_gemini(prompt, **kwargs):
        return '{"verdict": "APPROVE", "confidence": 80, "key_reasons": ["Healthy trend"]}'

    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_groq_http", mock_groq)
    monkeypatch.setattr("mjonai.agents.dual_model_ensemble._query_gemini_http", mock_gemini)

    res = query_dual_model_ensemble("Evaluate RELIANCE")
    assert res.verdict == "APPROVE"
    assert res.blended_confidence == 80
    assert res.model_a_verdict == "OFFLINE"
    assert res.model_b_verdict == "APPROVE"
