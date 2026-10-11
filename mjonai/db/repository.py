"""
Module: db/repository.py

Purpose: Central Database API Façade & Stable Public Persistence Gateway.
         Provides a unified, decoupled persistence interface for all application callers
         (main.py, execution/, risk/, strategy/, agents/, analytics/, communication/).

Architectural Role:
  1. Stable Public API Gateway (Decouples application logic from internal DB table organization).
  2. Explicit API Manifest (__all__) preventing namespace pollution and API drift.
  3. Lightweight Health & Telemetry Probe (get_repository_health).
  4. 100% Backwards-Compatible Public API for all 39 dependent callers.
"""

from datetime import datetime as _datetime, timezone as _timezone
import logging as _logging
import time as _time
from typing import Any as _Any, Dict as _Dict, List as _List, Optional as _Optional

# ── 1. DOMAIN SUBMODULE RE-EXPORTS ───────────────────────────────────────────

from mjonai.db.trades import (
    insert_trade,
    get_open_trades,
    get_open_trade_by_symbol,
    get_open_trade_by_symbol_strict,
    cancel_trade,
    get_trades_closed_today,
    get_all_trades_today,
    close_trade,
    update_trade_exit_fields,
    insert_trade_tranches,
    get_open_tranches,
    get_open_tranches_by_trade,
    get_closed_tranche_pnl,
    close_tranche,
    update_trade_sl,
    get_trades_with_open_tranches,
    update_trade_price_extremes,
    update_trade_research_fields,
    get_research_trades,
    get_all_closed_trades,
    replay_trade_journal,
    TradeRecord,
    TrancheRecord,
)

from mjonai.db.signals import (
    insert_signal,
    get_signals_today,
    insert_signal_intelligence,
    insert_signals_bulk,
    update_signal_outcome,
    get_signals_intelligence_today,
    get_signal_by_id,
    get_signals_needing_forward_returns,
    update_signal_forward_returns,
    get_signals_for_alphalens,
    get_signals_intelligence_recent,
    get_forward_returns_by_signal_ids,
    replay_signal_journal,
    SignalIntelligenceRecord,
)

from mjonai.db.agents import (
    insert_agent_log,
    insert_agent_logs_bulk,
    update_agent_log_outcome,
    get_agent_accuracy,
    get_all_agents_accuracy_summary,
    get_agent_telemetry_summary,
    get_agent_logs_for_calibration,
    evaluate_verdict_accuracy,
    replay_agent_journal,
    AgentLogRecord,
)

from mjonai.db.snapshots import (
    upsert_daily_snapshot,
    upsert_intraday_snapshot,
    get_snapshot_history,
    get_latest_snapshot,
    get_latest_snapshot_before,
    upsert_market_state,
    update_mqi_score,
    get_latest_market_state,
    save_peak_equity,
    load_peak_equity,
    get_current_drawdown_pct,
    reset_peak_equity_cache,
    replay_local_journal,
    PortfolioSnapshot,
    IntradaySnapshotRecord,
    MarketStateSnapshotRecord,
)

from mjonai.db.patterns import (
    get_pattern,
    upsert_pattern,
    update_pattern_outcome,
    get_failing_patterns,
    get_pattern_failures,
    generate_setup_hash,
    get_consecutive_losses,
    quarantine_pattern,
    reactivate_pattern,
    soft_delete_pattern,
    get_patterns_for_quarantine_eval,
    clear_pattern_cache,
    replay_pattern_journal,
    PatternMemoryRecord,
)

from mjonai.db.system import (
    insert_scan_log,
    get_scan_history,
    insert_health_log,
    get_health_summary,
    upsert_strategy_performance,
    get_strategy_performance,
    insert_weight_log,
    get_latest_weights,
    insert_risk_event,
    insert_system_log,
    replay_system_journal,
    ScanLogRecord,
    SystemHealthRecord,
    StrategyPerformanceRecord,
    AgentWeightRecord,
)

# Shared client proxy instance & connection management (for backward compatibility)
from mjonai.db.client import (
    sb,
    get_supabase_client,
    is_db_connected,
    ping_db,
    reset_db_client,
)

_logger = _logging.getLogger(__name__)


# ── 2. LIGHTWEIGHT REPOSITORY HEALTH PROBE ───────────────────────────────────

def get_repository_health(deep_check: bool = False) -> _Dict[str, _Any]:
    """
    Lightweight, non-throwing repository health and connectivity check.
    Used by Health Monitors, Startup Guards, and Pre-Trade Risk Gates.
    - Default (deep_check=False): Fast sub-millisecond passive connection check.
    - Deep (deep_check=True): Active round-trip network ping via ping_db().
    """
    start_time = _time.perf_counter()
    connected = is_db_connected()
    ping_ok = None

    if deep_check and connected:
        ping_ok = ping_db()

    latency_ms = round((_time.perf_counter() - start_time) * 1000, 2)
    is_healthy = connected and (ping_ok is True if deep_check else True)

    payload: _Dict[str, _Any] = {
        "status": "HEALTHY" if is_healthy else ("DEGRADED" if connected and deep_check and not ping_ok else "DISCONNECTED"),
        "is_connected": connected,
        "latency_ms": latency_ms,
        "submodules_loaded": 6,
        "facade_version": "2.0.0",
        "timestamp_utc": _datetime.now(_timezone.utc).isoformat(),
    }
    if deep_check:
        payload["ping_ok"] = ping_ok

    return payload


def replay_all_journals() -> _Dict[str, int]:
    """
    Execute durable WAL journal replay across all domains.
    Returns dictionary mapping domain name to count of replayed records.
    """
    results: _Dict[str, int] = {}
    try:
        results["trades"] = replay_trade_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] trades replay error: {e}")
        results["trades"] = 0

    try:
        results["signals"] = replay_signal_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] signals replay error: {e}")
        results["signals"] = 0

    try:
        results["agents"] = replay_agent_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] agents replay error: {e}")
        results["agents"] = 0

    try:
        results["snapshots"] = replay_local_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] snapshots replay error: {e}")
        results["snapshots"] = 0

    try:
        results["patterns"] = replay_pattern_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] patterns replay error: {e}")
        results["patterns"] = 0

    try:
        results["system"] = replay_system_journal() or 0
    except Exception as e:
        _logging.getLogger(__name__).warning(f"[replay_all_journals] system replay error: {e}")
        results["system"] = 0

    return results


# ── 3. EXPLICIT PUBLIC API MANIFEST (__all__) ────────────────────────────────

__all__ = [
    "replay_all_journals",
    # Trades domain (20 symbols)
    "insert_trade",
    "get_open_trades",
    "get_open_trade_by_symbol",
    "get_open_trade_by_symbol_strict",
    "cancel_trade",
    "get_trades_closed_today",
    "get_all_trades_today",
    "close_trade",
    "update_trade_exit_fields",
    "insert_trade_tranches",
    "get_open_tranches",
    "get_open_tranches_by_trade",
    "get_closed_tranche_pnl",
    "close_tranche",
    "update_trade_sl",
    "get_trades_with_open_tranches",
    "update_trade_price_extremes",
    "update_trade_research_fields",
    "get_research_trades",
    "get_all_closed_trades",
    "replay_trade_journal",
    "TradeRecord",
    "TrancheRecord",

    # Signals domain (14 symbols)
    "insert_signal",
    "get_signals_today",
    "insert_signal_intelligence",
    "insert_signals_bulk",
    "update_signal_outcome",
    "get_signals_intelligence_today",
    "get_signal_by_id",
    "get_signals_needing_forward_returns",
    "update_signal_forward_returns",
    "get_signals_for_alphalens",
    "get_signals_intelligence_recent",
    "get_forward_returns_by_signal_ids",
    "replay_signal_journal",
    "SignalIntelligenceRecord",

    # AI Agents domain (10 symbols)
    "insert_agent_log",
    "insert_agent_logs_bulk",
    "update_agent_log_outcome",
    "get_agent_accuracy",
    "get_all_agents_accuracy_summary",
    "get_agent_telemetry_summary",
    "get_agent_logs_for_calibration",
    "evaluate_verdict_accuracy",
    "replay_agent_journal",
    "AgentLogRecord",

    # Snapshots & Market State domain (15 symbols)
    "upsert_daily_snapshot",
    "upsert_intraday_snapshot",
    "get_snapshot_history",
    "get_latest_snapshot",
    "get_latest_snapshot_before",
    "upsert_market_state",
    "update_mqi_score",
    "get_latest_market_state",
    "save_peak_equity",
    "load_peak_equity",
    "get_current_drawdown_pct",
    "reset_peak_equity_cache",
    "replay_local_journal",
    "PortfolioSnapshot",
    "IntradaySnapshotRecord",
    "MarketStateSnapshotRecord",

    # Patterns domain (14 symbols)
    "get_pattern",
    "upsert_pattern",
    "update_pattern_outcome",
    "get_failing_patterns",
    "get_pattern_failures",
    "generate_setup_hash",
    "get_consecutive_losses",
    "quarantine_pattern",
    "reactivate_pattern",
    "soft_delete_pattern",
    "get_patterns_for_quarantine_eval",
    "clear_pattern_cache",
    "replay_pattern_journal",
    "PatternMemoryRecord",

    # System & Telemetry domain (15 symbols)
    "insert_scan_log",
    "get_scan_history",
    "insert_health_log",
    "get_health_summary",
    "upsert_strategy_performance",
    "get_strategy_performance",
    "insert_weight_log",
    "get_latest_weights",
    "insert_risk_event",
    "insert_system_log",
    "replay_system_journal",
    "ScanLogRecord",
    "SystemHealthRecord",
    "StrategyPerformanceRecord",
    "AgentWeightRecord",

    # Client & Health (6 symbols)
    "sb",
    "get_supabase_client",
    "is_db_connected",
    "ping_db",
    "reset_db_client",
    "get_repository_health",
]
