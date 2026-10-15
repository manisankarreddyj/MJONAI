"""
Batch sector-cap regression pins for strategy/signal_scanner.py.

Defect verified in the 2026-10-15 engine log (`logs15102926.txt`): Gate 3's hard
sector cap was evaluated against the PRE-BATCH `open_trades` snapshot, so a single
scan approved three FMCG setups (ITC, HINDUNILVR, TATACONSUM) against a count of
one and drove the book to 4/2. The scanner now folds each batch approval into the
cap-accounting view so later signals in the same scan see it.
"""

import sys
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import mjonai.strategy.signal_scanner as ss
from mjonai.strategy.config import evaluate_sector_limits

FMCG_SETUPS = [
    ("ITC", "S15_FIIShortSqueeze"),
    ("HINDUNILVR", "S15_FIIShortSqueeze"),
    ("TATACONSUM", "S15_FIIShortSqueeze"),
]


def _fake_setup(symbol: str, strategy_id: str):
    strat = SimpleNamespace(name=strategy_id, timeframe="SWING", is_active=True)
    result = {
        "symbol": symbol,
        "strategy_id": strategy_id,
        "signal_direction": "LONG",
        "confidence": 70.0,
    }
    return (strat, result, None)


def _run_scan_with_fmcg_batch(pre_batch_open):
    """
    Drive the real scan loop with the real sector-cap logic: the patched
    processor mirrors what the pipeline does on approval (append to
    approved_signals) and consults the LIVE evaluate_sector_limits against the
    very open_trades list the scanner threads through the batch.
    """
    decisions = []

    def _fake_processor(**kw):
        symbol = kw["clean_symbol"]
        open_trades = kw["open_trades"]
        res = evaluate_sector_limits(
            candidate_symbol=symbol,
            candidate_entry=400.0,
            candidate_qty=1,
            open_trades=open_trades,
        )
        decisions.append((symbol, res.is_allowed, res.reason))
        if not res.is_allowed:
            return False
        kw["approved_signals"].append({
            "symbol": symbol,
            "strategy_id": kw["strategy_result"].get("strategy_id"),
            "signal_direction": "LONG",
            "entry_price": 400.0,
            "quantity": 1,
            "stop_loss": 380.0,
            "target": 440.0,
        })
        return True

    def _fake_scan_single(symbol, *args, **kwargs):
        for sym, strat_id in FMCG_SETUPS:
            if sym == symbol:
                return [_fake_setup(sym, strat_id)]
        return []

    with patch("mjonai.strategy.signal_scanner.is_trading_allowed", return_value=True), \
         patch("mjonai.strategy.signal_scanner.get_open_trades", return_value=list(pre_batch_open)), \
         patch("mjonai.strategy.signal_scanner.get_universe", return_value=[s for s, _ in FMCG_SETUPS]), \
         patch("mjonai.strategy.signal_scanner._scan_single_symbol", side_effect=_fake_scan_single), \
         patch("mjonai.strategy.signal_scanner._process_single_strategy_signal", side_effect=_fake_processor), \
         patch("mjonai.strategy.signal_scanner.insert_scan_log"), \
         patch("mjonai.strategy.signal_scanner._dispatch_signal_alert"):
        result = ss.scan_signals(
            mqi_level="HIGH",
            signals_allowed=99,
            market_state="BULL",
            vix=14.0,
            system_mode="RESEARCH",
            timeframe="15m",
            max_workers=1,
        )
    return result, decisions


def test_batch_approvals_are_visible_to_sector_cap():
    """
    Three FMCG setups against one FMCG position already open: the FIRST new
    approval is allowed (2nd stock), the SECOND must be blocked by the hard
    Gate 3 sector cap — the batch must not be able to walk past it.
    """
    pre_batch = [{"symbol": "BRITANNIA", "entry_price": 400.0, "quantity": 1}]

    approved, decisions = _run_scan_with_fmcg_batch(pre_batch)

    # Exactly one new FMCG approval — the cap stopped the rest of the batch.
    assert [s["symbol"] for s in approved] == ["ITC"]

    blocked = [d for d in decisions if not d[1]]
    assert blocked, "no signal in the batch was sector-capped"
    assert all("Sector cap: 2/2 FMCG" in reason for _, _, reason in blocked)


def test_batch_fold_updates_cap_accounting_view():
    """The scanner threads a growing open_trades list into each evaluation."""
    pre_batch = []
    captured_views = []

    def _fake_processor(**kw):
        symbol = kw["clean_symbol"]
        captured_views.append([t.get("symbol") for t in kw["open_trades"]])
        kw["approved_signals"].append({
            "symbol": symbol,
            "strategy_id": kw["strategy_result"].get("strategy_id"),
            "signal_direction": "LONG",
            "entry_price": 400.0,
            "quantity": 1,
            "stop_loss": 380.0,
            "target": 440.0,
        })
        return True

    def _fake_scan_single(symbol, *args, **kwargs):
        for sym, strat_id in FMCG_SETUPS:
            if sym == symbol:
                return [_fake_setup(sym, strat_id)]
        return []

    with patch("mjonai.strategy.signal_scanner.is_trading_allowed", return_value=True), \
         patch("mjonai.strategy.signal_scanner.get_open_trades", return_value=list(pre_batch)), \
         patch("mjonai.strategy.signal_scanner.get_universe", return_value=[s for s, _ in FMCG_SETUPS]), \
         patch("mjonai.strategy.signal_scanner._scan_single_symbol", side_effect=_fake_scan_single), \
         patch("mjonai.strategy.signal_scanner._process_single_strategy_signal", side_effect=_fake_processor), \
         patch("mjonai.strategy.signal_scanner.insert_scan_log"), \
         patch("mjonai.strategy.signal_scanner._dispatch_signal_alert"):
        ss.scan_signals(
            mqi_level="HIGH", signals_allowed=99, market_state="BULL", vix=14.0,
            system_mode="RESEARCH", timeframe="15m", max_workers=1,
        )

    # Each evaluation saw every earlier batch approval, in order.
    assert captured_views[0] == []
    assert captured_views[1] == ["ITC"]
    assert captured_views[2] == ["ITC", "HINDUNILVR"]
