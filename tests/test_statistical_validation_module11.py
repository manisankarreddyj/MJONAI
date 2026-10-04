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
