import numpy as np
import pandas as pd
import pytest

from agents.quant_auditor import (
    audit_quantitative_integrity,
    QuantAuditorResult,
)


def test_quant_auditor_trend_breakout_evaluation():
    """Verify Quant Auditor evaluation on persistent trend breakout."""
    # Synthetic trending series with Hurst > 0.55
    closes = np.array([100 + i * 1.5 + np.sin(i) * 0.5 for i in range(50)])
    df = pd.DataFrame({"Close": closes, "Open": closes - 0.2, "High": closes + 0.5, "Low": closes - 0.5})

    signal = {
        "symbol": "RELIANCE",
        "strategy_id": "S01_MomentumRSI",
        "signal_direction": "LONG",
        "entry_price": float(closes[-1]),
    }

    res = audit_quantitative_integrity(signal, df=df)
    assert res["verdict"] in ("VERIFIED_ALPHA", "MODERATE_EDGE")
    assert res["conviction_score"] >= 60
    assert res["hurst_exponent"] > 0.0
    assert len(res["key_findings"]) >= 1


def test_quant_auditor_mean_reversion_evaluation():
    """Verify Quant Auditor evaluation on mean-reverting asset."""
    # Synthetic oscillating series
    closes = np.array([100 + np.sin(i * 0.8) * 5.0 for i in range(50)])
    df = pd.DataFrame({"Close": closes, "Open": closes, "High": closes + 1.0, "Low": closes - 1.0})

    signal = {
        "symbol": "TCS",
        "strategy_id": "S02_MeanReversion",
        "signal_direction": "LONG",
        "entry_price": float(closes[-1]),
    }

    res = audit_quantitative_integrity(signal, df=df)
    assert res["verdict"] in ("VERIFIED_ALPHA", "MODERATE_EDGE", "STATISTICAL_NOISE")
    assert "Hurst" in res["key_findings"][0]
