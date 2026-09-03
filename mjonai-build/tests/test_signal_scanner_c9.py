"""
Regression test for audit finding C9 (2026-08-25).

execute_signal_scan() referenced an unbound `strat_id` in the post-approval
cooldown branch. Python evaluates dict.get() defaults eagerly, so the first
approved signal under PAPER/LIVE raised NameError, aborted the entire scan
(the try block has no except), and no trade ever reached execute_order.
RESEARCH mode skips the branch, which is why the full suite stayed green.

This test pins the NON-RESEARCH scan path end-to-end with sealed seams:
a fake strategy hit is injected, the pipeline seam approves it, and the
cooldown ledger must record exactly one entry instead of raising.
"""

from types import SimpleNamespace

import pandas as pd
import pytest

import strategy.signal_scanner as ss


@pytest.fixture()
def paper_env(monkeypatch):
    """Seal every external seam of execute_signal_scan; return cooldown spy."""
    recorded = {"cooldowns": []}

    monkeypatch.setattr(ss, "is_trading_allowed", lambda *a, **k: True)
    monkeypatch.setattr(ss, "get_open_trades", lambda *a, **k: [])

    fake_hit = (
        SimpleNamespace(name="S01_MomentumRSI"),
        {"strategy_id": "S01_MomentumRSI", "confidence": 90.0,
         "technical_score": 90.0, "symbol": "SMOKE"},
        pd.DataFrame({"Close": [1.0]}),  # df unused once pipeline is sealed
    )
    monkeypatch.setattr(ss, "_scan_single_symbol", lambda *a, **k: [fake_hit])

    def fake_pipeline(**kwargs):
        kwargs["approved_signals"].append(
            {"symbol": kwargs["clean_symbol"], "strategy_id": "S01_MomentumRSI"})
        return True

    monkeypatch.setattr(ss, "_process_single_strategy_signal", fake_pipeline)
    monkeypatch.setattr(
        ss, "_record_cooldown",
        lambda symbol, strategy_id: recorded["cooldowns"].append((symbol, strategy_id)))
    monkeypatch.setattr(ss, "insert_scan_log", lambda payload: None)
    monkeypatch.setattr(ss, "_dispatch_signal_alert", lambda sig: None)
    return recorded


def test_paper_mode_approval_records_cooldown_without_nameerror(paper_env):
    result = ss.execute_signal_scan(
        mqi_level="MEDIUM",
        signals_allowed=1,
        market_state="NEUTRAL",
        vix=15.0,
        live_prices={},
        symbol_map={},
        system_mode="PAPER",
    )
    assert result.signals_approved == 1
    assert paper_env["cooldowns"] == [("SMOKE", "S01_MomentumRSI")]


def test_research_mode_still_skips_cooldown_branch(paper_env):
    result = ss.execute_signal_scan(
        mqi_level="MEDIUM",
        signals_allowed=20,
        market_state="NEUTRAL",
        vix=15.0,
        live_prices={},
        symbol_map={},
        system_mode="RESEARCH",
    )
    assert result.signals_approved >= 1
    assert paper_env["cooldowns"] == []
