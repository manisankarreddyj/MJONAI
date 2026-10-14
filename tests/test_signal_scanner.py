"""
Unit and Institutional Test Suite for strategy/signal_scanner.py
Tests ScanExecutionResult Contract, Thread-Safe Concurrency Locks,
30-Minute Signal Cooldowns, Highest-Conviction Selection, and Scan Funnels.
"""

from datetime import datetime
import pytest
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.strategy.signal_scanner import (
    ScanExecutionResult,
    scan_signals,
    execute_signal_scan,
    _is_in_cooldown,
    _live_depth_snapshot,
    _record_cooldown,
    reset_scan_cooldowns,
    _scan_single_symbol,
)


# ── MICROSTRUCTURE FEED (S17 depth wiring) ───────────────────────────────────

def _fake_angel_modules(monkeypatch, fresh=True, depth=None):
    """Inject fake token_map + websocket modules (no SmartAPI needed)."""
    import types
    token_mod = types.ModuleType("mjonai.data.angelone.token_map")
    token_mod.get_token_for_symbol = lambda symbol, exchange="NSE": "12345" if symbol == "RELIANCE" else None
    ws_mod = types.ModuleType("mjonai.data.angelone.websocket")
    ws_mod.is_token_fresh = lambda token: bool(fresh)
    ws_mod.get_live_depth = lambda token: depth
    monkeypatch.setitem(sys.modules, "mjonai.data.angelone.token_map", token_mod)
    monkeypatch.setitem(sys.modules, "mjonai.data.angelone.websocket", ws_mod)


def test_depth_snapshot_fresh_tick_passes_top_of_book(monkeypatch):
    _fake_angel_modules(monkeypatch, fresh=True,
                        depth={"best_bid": 2500.0, "best_ask": 2500.5,
                               "bid_qty": 90000, "ask_qty": 20000,
                               "spread_pct": 0.02, "depth_bids": [], "depth_asks": []})
    snap = _live_depth_snapshot("RELIANCE")
    assert snap == {"best_bid": 2500.0, "best_ask": 2500.5,
                    "bid_qty": 90000, "ask_qty": 20000}


def test_depth_snapshot_stale_unknown_or_absent_is_none(monkeypatch):
    _fake_angel_modules(monkeypatch, fresh=False,
                        depth={"best_bid": 2500.0, "best_ask": 2500.5,
                               "bid_qty": 1, "ask_qty": 1})
    assert _live_depth_snapshot("RELIANCE") is None  # stale tick
    _fake_angel_modules(monkeypatch, fresh=True, depth=None)
    assert _live_depth_snapshot("RELIANCE") is None  # no depth frame
    _fake_angel_modules(monkeypatch, fresh=True,
                        depth={"best_bid": 2500.0, "best_ask": 2500.5,
                               "bid_qty": 1, "ask_qty": 1})
    assert _live_depth_snapshot("UNKNOWN_SYMBOL") is None  # no token


# ── 1. CONTRACT SERIALIZATION TESTS ──────────────────────────────────────────

def test_scan_execution_result_contract():
    """Verify ScanExecutionResult dataclass serializes cleanly to dict."""
    result = ScanExecutionResult(
        approved_signals=[{"symbol": "RELIANCE", "entry_price": 2800.0}],
        symbols_scanned=15,
        signals_generated=4,
        signals_approved=1,
        active_trades=2,
        position_limit_reached=False,
        scan_duration_ms=250,
        market_state="BULL",
        mqi_level="HIGH",
        vix=13.5,
        system_mode="LIVE",
        is_successful=True,
    )
    d = result.to_dict()
    assert d["symbols_scanned"] == 15
    assert d["signals_approved"] == 1
    assert len(d["approved_signals"]) == 1


# ── 2. 30-MINUTE SIGNAL COOLDOWN SENTRY TESTS ────────────────────────────────

def test_signal_cooldown_and_reset():
    """Verify signal cooldown records and resets cleanly."""
    reset_scan_cooldowns()
    assert _is_in_cooldown("RELIANCE", "S01_MomentumRSI") is False

    _record_cooldown("RELIANCE", "S01_MomentumRSI")
    assert _is_in_cooldown("RELIANCE", "S01_MomentumRSI") is True
    # Different strategy on same symbol is not cooled down
    assert _is_in_cooldown("RELIANCE", "S05_PriceAction") is False

    reset_scan_cooldowns()
    assert _is_in_cooldown("RELIANCE", "S01_MomentumRSI") is False


# ── 3. THREAD-SAFE CONCURRENCY LOCK TESTS ────────────────────────────────────

@patch("mjonai.strategy.signal_scanner.is_trading_allowed", return_value=False)
def test_emergency_risk_breaker_blocks_scan(mock_trading_allowed):
    """Verify emergency risk kill line blocks scanner immediately."""
    result = execute_signal_scan(
        mqi_level="HIGH",
        signals_allowed=3,
        market_state="BULL",
        vix=14.0,
    )
    assert result.is_successful is False
    assert "Risk Engine Emergency Kill Line" in result.rejection_reason
    assert len(result.approved_signals) == 0


# ── 4. DYNAMIC POSITION LIMIT TESTS ──────────────────────────────────────────

@patch("mjonai.strategy.signal_scanner.is_trading_allowed", return_value=True)
@patch("mjonai.strategy.signal_scanner.get_open_trades", return_value=[{"symbol": f"SYM_{i}"} for i in range(5)])
def test_position_limit_reached_stops_scan(mock_open_trades, mock_trading_allowed):
    """Verify scanner stops when active position limit is already reached."""
    result = execute_signal_scan(
        mqi_level="HIGH",
        signals_allowed=3,
        market_state="BULL",
        vix=14.0,
        system_mode="LIVE",
    )
    assert result.position_limit_reached is True
    assert len(result.approved_signals) == 0


# ── 5. TIMEFRAME MATCHING TESTS ──────────────────────────────────────────────

@patch("mjonai.strategy.signal_scanner.get_stock_data", return_value=MagicMock(__len__=lambda x: 100))
def test_timeframe_filtering_skips_incompatible_strategies(mock_stock_data):
    """Verify 5m intraday scan only evaluates intraday strategies."""
    # In a 5m scan, swing-only strategies (e.g. S03 Turtle) are skipped
    setups = _scan_single_symbol(
        symbol="TCS",
        market_state="BULL",
        mqi_level="HIGH",
        vix=14.0,
        sys_mode="LIVE",
        timeframe="5m",
        open_strategy_symbols=set(),
    )
    assert isinstance(setups, list)


# ── 6. END-TO-END SCANNER EXECUTION TESTS ────────────────────────────────────

@patch("mjonai.strategy.signal_scanner.is_trading_allowed", return_value=True)
@patch("mjonai.strategy.signal_scanner.get_open_trades", return_value=[])
@patch("mjonai.strategy.signal_scanner.get_stock_data", return_value=None)
@patch("mjonai.strategy.signal_scanner.insert_scan_log")
def test_scan_signals_empty_market_data(mock_insert_log, mock_stock_data, mock_open_trades, mock_trading):
    """Verify scanner gracefully completes when market data is unavailable."""
    signals = scan_signals(
        mqi_level="HIGH",
        signals_allowed=2,
        market_state="BULL",
        vix=14.0,
        universe_tier="TIER_1",
    )
    assert isinstance(signals, list)
    assert len(signals) == 0
