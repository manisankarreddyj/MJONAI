"""
Test Suite: tests/test_statistical_validation_module11.py
Purpose: Verify Deflated Sharpe Ratio (DSR), Probabilistic Sharpe Ratio (PSR),
         Harvey-Liu Haircut Sharpe Ratio, and Stationary Block Bootstrap.
"""

import math
import ast
import pytest
from pathlib import Path

from mjonai.analytics.statistical_validation import (
    deflated_sharpe_ratio,
    deflated_sharpe_pvalue,
    probabilistic_sharpe_ratio,
    haircut_sharpe_ratio,
    stationary_block_bootstrap,
    bonferroni_adjusted,
    benjamini_hochberg_adjusted,
    benjamini_yekutieli_adjusted,
    fdr_reject,
    apply_fdr_to_family,
    probability_of_backtest_overfit,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


def test_sharpe_validation_family_has_a_single_home():
    """No Sharpe-validation function may be defined twice under the same name.

    A duplicate `deflated_sharpe_ratio` lived in `strategy/registry/quant_math.py`
    until 2026-10-04. It was not a harmless copy: it took a precomputed Sharpe
    and returned a p-VALUE in [0, 1], while the canonical version takes a return
    series and returns an unbounded z-SCORE. Two same-named callables with
    different signatures AND different return types is a silent misreading trap,
    so the duplication itself is now pinned shut.
    """
    tracked = {
        "deflated_sharpe_ratio",
        "deflated_sharpe_pvalue",
        "probabilistic_sharpe_ratio",
        "haircut_sharpe_ratio",
    }
    defined: dict[str, list[str]] = {}
    unparseable: list[str] = []
    for py in REPO_ROOT.rglob("*.py"):
        if "__pycache__" in py.parts or ".venv" in py.parts or "archive" in py.parts:
            continue
        try:
            # utf-8-sig, NOT utf-8: a BOM (which PowerShell's -Encoding UTF8
            # writes) makes ast.parse raise SyntaxError, and silently skipping
            # such a file would exempt it from the pin entirely.
            tree = ast.parse(py.read_text(encoding="utf-8-sig"), filename=str(py))
        except OSError:
            continue
        except SyntaxError as exc:
            unparseable.append(f"{py.relative_to(REPO_ROOT).as_posix()}: {exc}")
            continue
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name in tracked:
                defined.setdefault(node.name, []).append(
                    py.relative_to(REPO_ROOT).as_posix()
                )

    assert not unparseable, (
        "source files could not be parsed and would escape this audit "
        f"silently: {unparseable}"
    )
    duplicates = {n: p for n, p in defined.items() if len(p) > 1}
    assert not duplicates, f"Sharpe-validation functions defined more than once: {duplicates}"
    # The canonical module owns all of them.
    for name, paths in defined.items():
        assert paths == ["mjonai/analytics/statistical_validation.py"], (
            f"{name} must live only in mjonai/analytics/statistical_validation.py, found {paths}"
        )


def test_quant_math_no_longer_exports_a_deflated_sharpe():
    """quant_math is a quantitative-math toolbox, not a Sharpe-statistics home."""
    import mjonai.strategy.registry.quant_math as qm

    for gone in ("deflated_sharpe_ratio", "deflated_sharpe_pvalue"):
        assert not hasattr(qm, gone), (
            f"quant_math.{gone} was consolidated into "
            "mjonai.analytics.statistical_validation on 2026-10-04"
        )


def test_the_two_dsr_forms_are_distinct_and_correctly_typed():
    """The z-score and p-value forms answer different questions and must not be
    confused: one is unbounded and may be negative, the other lives in [0, 1]."""
    rets = [0.01 + (i % 5) * 0.004 - 0.002 for i in range(300)]
    z = deflated_sharpe_ratio(rets, num_trials=10)
    p = deflated_sharpe_pvalue(sharpe_ratio=2.5, num_trials=10, sample_length=252)

    assert 0.0 <= p <= 1.0, "p-value form must be a probability"
    assert isinstance(z, float) and isinstance(p, float)

    # A clearly strong Sharpe over few trials is significant in p-value form.
    assert p >= 0.95
    # A marginal Sharpe over many trials is not.
    assert deflated_sharpe_pvalue(
        sharpe_ratio=0.6, num_trials=500, sample_length=100
    ) < 0.50

    # The z-score form is signed: a losing series must fall below zero.
    losing = [-0.01 + (i % 5) * 0.004 - 0.002 for i in range(300)]
    assert deflated_sharpe_ratio(losing, num_trials=10) < 0.0


def test_probabilistic_sharpe_ratio_bounds():
    """Verify PSR is bounded in [0.0, 1.0] and scales monotonically with Sharpe ratio."""
    # Positive daily returns
    good_returns = [0.01 + (i % 3) * 0.005 for i in range(100)]
    psr_good = probabilistic_sharpe_ratio(good_returns, benchmark_sr=0.0)
    assert 0.0 <= psr_good <= 1.0
    assert psr_good > 0.90  # Extremely high probability that SR > 0

    # Negative daily returns
    bad_returns = [-0.01 - (i % 3) * 0.005 for i in range(100)]
    psr_bad = probabilistic_sharpe_ratio(bad_returns, benchmark_sr=0.0)
    assert 0.0 <= psr_bad <= 1.0
    assert psr_bad < 0.10


def test_haircut_sharpe_ratio_discount():
    """Verify Harvey-Liu Haircut applies increasing discount with more factor trials."""
    h1 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=1)
    assert h1["haircut_sr"] == 2.0
    assert h1["discount_pct"] == 0.0

    h20 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=20)
    assert h20["haircut_sr"] < 2.0
    assert h20["discount_pct"] > 0.0

    h100 = haircut_sharpe_ratio(observed_sr=2.0, num_trials=100)
    assert h100["haircut_sr"] < h20["haircut_sr"]
    assert h100["discount_pct"] > h20["discount_pct"]


def test_stationary_block_bootstrap_preserves_length():
    """Verify stationary block bootstrap resamples full sequence length."""
    data = [1.0, 2.0, 3.0, 4.0, 5.0, 6.0, 7.0, 8.0, 9.0, 10.0]
    samples = stationary_block_bootstrap(data, avg_block_size=3, num_samples=50)
    assert len(samples) == 50
    for s in samples:
        assert len(s) == len(data)


def test_bonferroni_adjusted_known_values():
    """Bonferroni: adj = min(1, p*m), elementwise, no monotonicity step."""
    assert bonferroni_adjusted([]) == []
    assert bonferroni_adjusted([0.03]) == [0.03]
    assert bonferroni_adjusted([0.01, 0.04, 0.03, 0.2]) == [0.04, 0.16, 0.12, 0.8]
    # Capped at 1.0, never above.
    assert bonferroni_adjusted([0.9, 0.9]) == [1.0, 1.0]
    # Non-finite / out-of-range inputs are least-significant, never significant.
    assert bonferroni_adjusted([float("nan"), 2.0, -1.0]) == [1.0, 1.0, 0.0]


def test_benjamini_hochberg_adjusted_known_values():
    """BH step-up on [0.01, 0.04, 0.03, 0.2] -> [0.04, 0.0533, 0.0533, 0.2]."""
    assert benjamini_hochberg_adjusted([]) == []
    assert benjamini_hochberg_adjusted([0.03]) == [0.03]
    got = benjamini_hochberg_adjusted([0.01, 0.04, 0.03, 0.2])
    assert got == [0.04, 0.0533, 0.0533, 0.2]
    # Monotonicity: the middle ranks collapse to the tighter bound.
    assert got[1] == got[2] <= got[3]
    # Order-preserving: output aligns with the caller's input order.
    assert benjamini_hochberg_adjusted([0.2, 0.01]) == [0.2, 0.02]


def test_benjamini_yekutieli_dominates_bh():
    """BY holds under arbitrary dependence, so BY >= BH pointwise, capped at 1."""
    ps = [0.01, 0.04, 0.03, 0.2]
    bh = benjamini_hochberg_adjusted(ps)
    by_ = benjamini_yekutieli_adjusted(ps)
    assert by_ == [0.0833, 0.1111, 0.1111, 0.4167]
    assert all(b >= a for a, b in zip(bh, by_))
    assert all(0.0 <= q <= 1.0 for q in by_)
    assert benjamini_yekutieli_adjusted([]) == []


def test_fdr_reject_threshold_and_method_gate():
    """BH at alpha=0.05 rejects only the 0.01 arm of the worked example."""
    ps = [0.01, 0.04, 0.03, 0.2]
    assert fdr_reject(ps, alpha=0.05, method="bh") == [True, False, False, False]
    assert fdr_reject(ps, alpha=0.05, method="bonferroni") == [True, False, False, False]
    # BY is stricter here: nothing survives at 5%.
    assert fdr_reject(ps, alpha=0.05, method="by") == [False, False, False, False]
    with pytest.raises(ValueError):
        fdr_reject(ps, alpha=0.05, method="holm")
    with pytest.raises(ValueError):
        fdr_reject(ps, alpha=1.5)


def test_apply_fdr_to_family_is_disclosure_not_mutation():
    """Family rows gain BH/BY/Bonferroni columns; inputs are never mutated."""
    rows = [
        {"config": "a", "WRC_p": 0.01},
        {"config": "b", "WRC_p": 0.04},
        {"config": "c"},  # absent p -> least significant, never significant
    ]
    out = apply_fdr_to_family(rows)
    assert len(out) == 3
    assert out[0]["WRC_p_bh"] == 0.03
    assert out[2]["WRC_p_bh"] == 1.0
    assert out[2]["fdr_bh_significant"] is False
    assert "WRC_p_bh" not in rows[0], "input rows must not be mutated"
    # JSON-safe floats only.
    import json as _json
    _json.dumps(out)


def test_pbo_zero_when_is_best_generalises():
    """Every split's IS-best is also OOS-best -> PBO 0."""
    is_m = [[1.0, 2.0, 3.0], [0.5, 1.5, 2.5]]
    oos_m = [[0.1, 0.2, 0.9], [0.0, 0.1, 0.8]]
    out = probability_of_backtest_overfit(is_m, oos_m)
    assert out["pbo"] == 0.0
    assert out["splits"] == 2 and out["trials"] == 3
    assert out["mean_logit"] > 0.0


def test_pbo_one_when_is_best_collapses_out_of_sample():
    """Every split's IS-best is OOS-worst -> PBO 1."""
    is_m = [[1.0, 2.0, 3.0], [0.5, 1.5, 2.5]]
    oos_m = [[0.9, 0.2, 0.1], [0.8, 0.1, 0.0]]
    out = probability_of_backtest_overfit(is_m, oos_m)
    assert out["pbo"] == 1.0
    assert out["splits"] == 2 and out["trials"] == 3
    assert out["mean_logit"] < 0.0


def test_pbo_maximal_doubt_on_thin_or_ragged_input():
    """<2 usable splits -> pbo=1.0 (doubt), never a clean bill; ragged raises."""
    assert probability_of_backtest_overfit([[1.0, 2.0]], [[0.5, 0.4]])["pbo"] == 1.0
    assert probability_of_backtest_overfit([], [])["pbo"] == 1.0
    # Non-finite pairs drop out; a split left with <2 pairs is skipped.
    out = probability_of_backtest_overfit(
        [[1.0, float("nan")], [0.5, 1.5, 2.5]],
        [[0.5, 0.4], [0.0, 0.1, 0.8]],
    )
    assert out["pbo"] == 1.0 and out["splits"] == 1
    with pytest.raises(ValueError):
        probability_of_backtest_overfit([[1.0, 2.0]], [[0.5]])
