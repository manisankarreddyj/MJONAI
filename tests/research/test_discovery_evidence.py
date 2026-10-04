"""Regression tests: option-chain evidence features (research/discovery/evidence.py).

These pin the HONESTY contract of the feature builder, which feeds the first
real test of MJONAI's evidence-layer thesis (docs section 3):

  - no BaseStrategy is defined here and the registry is never imported, so the
    research-only boundary in tests/test_architecture_rules.py holds;
  - gamma and IV are delegated to the canonical engines, never reimplemented;
  - features fail closed (flat / absent), never imputed or fabricated.

The builders are exercised against synthetic frames so the suite stays offline.
"""
import ast
import inspect
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]  # tests/research/ -> repo root

from mjonai.research.discovery import evidence as EV  # noqa: E402


def test_evidence_module_defines_no_strategy_and_imports_no_registry():
    src = (REPO_ROOT / "mjonai" / "research" / "discovery" / "evidence.py").read_text(
        encoding="utf-8-sig"
    )
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            for base in node.bases:
                name = base.id if isinstance(base, ast.Name) else getattr(base, "attr", "")
                assert "BaseStrategy" not in name, (
                    "evidence.py is research-only and must not define a strategy"
                )
        if isinstance(node, ast.ImportFrom) and node.module:
            assert "strategy.registry" not in node.module, (
                "evidence.py must not depend on tradable strategy logic"
            )


def test_evidence_delegates_to_canonical_greeks_and_gex():
    """Gamma and IV must come from the single canonical implementations."""
    import mjonai.data.derivatives.gex_engine as gex
    import mjonai.options.greeks as greeks

    assert EV.calculate_gamma_exposure is gex.calculate_gamma_exposure
    assert EV.calculate_implied_volatility is greeks.calculate_implied_volatility


def test_max_pain_picks_the_strike_that_minimises_writer_pnl():
    """Max pain is the strike minimising total writer P&L at expiry."""
    # Heavy put OI at 100 and call OI at 120 => pain sits between them.
    strikes = np.array([90.0, 100.0, 110.0, 120.0])
    call_oi = np.array([0.0, 0.0, 0.0, 1000.0])
    put_oi = np.array([0.0, 1000.0, 0.0, 0.0])
    pain = EV._max_pain(strikes, call_oi, put_oi)
    assert 100.0 <= pain <= 120.0
    # At the pain strike, writer P&L must be <= that of a far-away strike.
    def pnl(k):
        return float(np.sum((k - strikes) * call_oi) + np.sum((strikes - k) * put_oi))
    assert pnl(pain) <= pnl(100.0) + 1e-9
    assert pnl(pain) <= pnl(120.0) + 1e-9


def test_max_pain_empty_chain_is_nan_not_zero():
    assert np.isnan(EV._max_pain(np.array([]), np.array([]), np.array([])))


def test_chain_root_is_portable_not_hardcoded():
    """Must resolve through research_paths, never an absolute D:\\ literal."""
    src = inspect.getsource(EV)
    assert "D:\\MJONAI" not in src and "D:/MJONAI" not in src, (
        "evidence.py must resolve the warehouse via configs/research_paths.py"
    )
    root = EV.chain_root()
    assert root.name == "eod" and root.parent.name == "fno_chain"


def test_build_evidence_fails_closed_on_empty_warehouse(tmp_path):
    """A warehouse with no matching months yields an empty frame, never zeros."""
    out = EV.build_evidence("NIFTY", "2019-01-01", "2019-12-31", chain_dir=tmp_path)
    assert isinstance(out, pd.DataFrame)
    assert out.empty, "absent data must produce no rows, not fabricated rows"