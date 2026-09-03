"""
12-Dimensional Production Test Suite for db/repository.py
Tests Public API Manifest (__all__), Submodule API Drift Detection,
Delegation Contracts, Lightweight Health Probes, and Caller Regression Sweeps.
"""

import inspect
import pytest
import sys
from pathlib import Path

# Add project root to sys.path
root_dir = Path(__file__).resolve().parent.parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

import db.repository as repo
import db.trades as trades
import db.signals as signals
import db.agents as agents
import db.snapshots as snapshots
import db.patterns as patterns
import db.system as system
import db.client as client


# ── 1. PUBLIC API MANIFEST (__all__) COMPLETENESS ────────────────────────────

def test_manifest_all_symbols_exist():
    """Verify that every single symbol listed in __all__ exists and is accessible on db.repository."""
    assert hasattr(repo, "__all__")
    assert len(repo.__all__) >= 50

    for symbol_name in repo.__all__:
        assert hasattr(repo, symbol_name), f"Exported symbol '{symbol_name}' missing from repository module!"


def test_no_unintended_public_exports():
    """Verify that no unexpected public (non-underscore) callables leak into repository namespace without being in __all__."""
    module_exports = set(repo.__all__)
    for name, obj in inspect.getmembers(repo):
        if not name.startswith("_") and not inspect.ismodule(obj):
            assert name in module_exports, f"Unintended public symbol '{name}' exposed without being in __all__!"


# ── 2. SUBMODULE API DRIFT DETECTION ENGINE ──────────────────────────────────

def test_submodule_api_drift_detection():
    """
    CRITICAL ARCHITECTURAL TEST:
    Automatically sweeps all 6 underlying domain submodules and verifies that every
    public function defined in those submodules is re-exported in db.repository.
    Catches any future submodule API drift immediately!
    """
    domain_submodules = [trades, signals, agents, snapshots, patterns, system]
    repo_manifest = set(repo.__all__)
    drift_missing_symbols = []

    for submodule in domain_submodules:
        submodule_name = submodule.__name__
        for attr_name, attr_value in inspect.getmembers(submodule):
            # Check for public functions defined directly in the submodule
            if inspect.isfunction(attr_value) and not attr_name.startswith("_"):
                # Only check functions belonging to db package (exclude third-party imports)
                if attr_value.__module__.startswith("db."):
                    if attr_name not in repo_manifest:
                        drift_missing_symbols.append((submodule_name, attr_name))

    assert len(drift_missing_symbols) == 0, (
        f"API Drift Detected! The following functions in submodules are missing from db.repository.__all__:\n"
        + "\n".join(f" - {mod}.{fn}" for mod, fn in drift_missing_symbols)
    )


# ── 3. DELEGATION CONTRACT VERIFICATION ──────────────────────────────────────

def test_delegation_contracts():
    """Verify that calling functions through repository delegates to domain submodules."""
    # Trades domain delegation
    assert repo.insert_trade is trades.insert_trade
    assert repo.get_open_trades is trades.get_open_trades
    assert repo.close_trade is trades.close_trade

    # Signals domain delegation
    assert repo.insert_signal is signals.insert_signal
    assert repo.get_signals_today is signals.get_signals_today

    # Agents domain delegation
    assert repo.insert_agent_log is agents.insert_agent_log
    assert repo.get_agent_accuracy is agents.get_agent_accuracy

    # Snapshots domain delegation
    assert repo.upsert_daily_snapshot is snapshots.upsert_daily_snapshot
    assert repo.get_latest_market_state is snapshots.get_latest_market_state

    # Patterns domain delegation
    assert repo.get_pattern is patterns.get_pattern
    assert repo.get_pattern_failures is patterns.get_pattern_failures

    # System domain delegation
    assert repo.insert_health_log is system.insert_health_log
    assert repo.get_latest_weights is system.get_latest_weights

    # Client delegation
    assert repo.sb is client.sb
    assert repo.is_db_connected is client.is_db_connected
    assert repo.ping_db is client.ping_db


# ── 4. LIGHTWEIGHT HEALTH PROBE VERIFICATION ─────────────────────────────────

def test_repository_health_probe():
    """Verify get_repository_health() returns structured diagnostic metadata without throwing."""
    health = repo.get_repository_health(deep_check=False)
    assert isinstance(health, dict)
    assert "status" in health
    assert "is_connected" in health
    assert "latency_ms" in health
    assert "submodules_loaded" in health
    assert health["submodules_loaded"] == 6
    assert health["facade_version"] == "2.0.0"

    # Deep check test
    health_deep = repo.get_repository_health(deep_check=True)
    assert "ping_ok" in health_deep
    assert "timestamp_utc" in health
    assert health["latency_ms"] >= 0.0


# ── 5. CALLER REGRESSION & RESOLUTION SWEEP ──────────────────────────────────

def test_critical_callers_symbol_resolution():
    """Verify key functions required by main.py, risk/, strategy/, and execution/ resolve properly."""
    # main.py requirements
    assert callable(repo.get_open_trades)
    assert callable(repo.get_latest_market_state)
    assert callable(repo.get_signals_intelligence_today)

    # risk/ requirements
    assert callable(repo.save_peak_equity)
    assert callable(repo.load_peak_equity)
    assert callable(repo.insert_risk_event)

    # strategy/ & execution/ requirements
    assert callable(repo.insert_trade)
    assert callable(repo.close_trade)
    assert callable(repo.update_trade_sl)
    assert callable(repo.insert_trade_tranches)
