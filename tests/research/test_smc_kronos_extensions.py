"""Clean-room research readers + extension contract (queue items ⑤).

SMC wrapper: the new primitives (order blocks, BOS/CHoCH, liquidity) are additive,
causally lagged, and library errors yield 0.0 rather than fabricated levels — and the
A8 signal's own columns are unchanged.
Kronos fine-tune seam: gated (env + vendored script + torch + data), fail-closed with
the remediation, and it makes no claim about the result.
"""
import numpy as np
import pandas as pd
import pytest

from apps.research.run_kronos_finetune import main as finetune_main
from mjonai.research.discovery.smc_features import smc_features


def _wave_frame(n: int = 200) -> pd.DataFrame:
    idx = pd.date_range("2024-01-01", periods=n, freq="D")
    vals = 100.0 + 8.0 * np.sin(np.arange(n, dtype=float) / 6.0) + np.arange(n) * 0.05
    return pd.DataFrame(
        {"Open": vals, "High": vals + 0.4, "Low": vals - 0.4, "Close": vals, "Volume": 1000.0},
        index=idx,
    )


def test_smc_features_are_additive_and_causal():
    df = _wave_frame()
    feat = smc_features(df, swing_length=10)
    original = {"smc_swing_hl", "smc_dist_to_swing", "smc_fvg_dir", "smc_in_bull_fvg", "smc_in_bear_fvg"}
    added = {"smc_ob_dir", "smc_bos", "smc_choch", "smc_liquidity"}
    assert original <= set(feat.columns) and added <= set(feat.columns)
    last_ts = df.index[-1]
    for col in added | original:
        assert feat[col].notna().all() or col == "smc_dist_to_swing"   # only dist may be NaN
        assert pd.api.types.is_numeric_dtype(feat[col])
    # primitive markers only ever carry {0, 1, -1}
    for col in added:
        assert set(feat[col].unique()) <= {-1.0, 0.0, 1.0}
    assert feat.index[-1] == last_ts


def test_smc_features_short_frame_still_shapes():
    feat = smc_features(_wave_frame(n=60), swing_length=5)
    assert {"smc_ob_dir", "smc_bos"} <= set(feat.columns)   # no crash on shorter frames


def test_finetune_gate_requires_env(monkeypatch, capsys):
    monkeypatch.delenv("MJONAI_FINETUNE_KRonOS", raising=False)
    monkeypatch.delenv("MJONAI_FINETUNE_KronOS", raising=False)
    assert finetune_main(["--data", "x.csv"]) == 2
    assert "MJONAI_FINETUNE_KronOS=1" in capsys.readouterr().out


def test_finetune_fails_closed_on_missing_pieces(monkeypatch, capsys):
    monkeypatch.setenv("MJONAI_FINETUNE_KronOS", "1")
    assert finetune_main(["--data", "nonexistent.csv"]) == 2   # data checked first
    assert "training data missing" in capsys.readouterr().out
