"""
Module: db/snapshots.py

Purpose: Daily Portfolio Snapshots, Intraday Risk Checkpoints, Market State History,
         MQI Level Persistence, Peak Equity High-Watermark State Integrity,
         Real-Time Drawdown Tracking, and Offline WAL Journal Replay.

Architectural Principles:
  1. Accounting & Capital State Integrity (daily equity curves, allocations, P&L).
  2. Intraday Checkpoint Auditing (margin utilization, open positions, unrealized P&L).
  3. Market Intelligence Persistence (macro regimes, Nifty price/EMA200, VIX, MQI).
  4. Risk-Control Watermark Protection (Mathematical monotonicity for 15% Kill Line).
  5. Real-Time High-Watermark Drawdown Profiling (get_current_drawdown_pct).
  6. Local Durable Journaling & Automated WAL Replay Protocol (replay_local_journal).
  7. Financial Float Sanitization (NaN/Inf -> None conversion without PostgreSQL errors).
  8. Resilient Database Persistence with Exponential Backoff Retries.
  9. Type-Safe Immutable Snapshot Data Contracts (PortfolioSnapshot, IntradaySnapshotRecord, MarketStateSnapshotRecord).
 10. 100% Backwards-Compatible Public API for all dependent callers.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from mjonai.db.client import sb, is_db_connected, execute_with_retry as _execute_with_retry

logger = logging.getLogger(__name__)

# Local durable journal directory
_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"  # repo root (ADR-0008)
_PEAK_EQUITY_FILE = _STORAGE_DIR / "peak_equity.json"
_LOCAL_JOURNAL_FILE = _STORAGE_DIR / "snapshots_journal.jsonl"

# In-memory monotonicity cache for peak equity
_CACHED_PEAK_EQUITY: Optional[float] = None


# ── 1. TYPE-SAFE IMMUTABLE SNAPSHOT DATA CONTRACTS ───────────────────────────

@dataclass(frozen=True)
class PortfolioSnapshot:
    """Immutable contract for EOD portfolio performance snapshots."""
    snapshot_date: str
    capital_total: float
    cash_balance: float
    margin_used: float = 0.0
    daily_pnl: float = 0.0
    daily_pnl_pct: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float = 0.0
    drawdown_pct: float = 0.0
    open_positions: int = 0
    closed_trades: int = 0
    win_count: int = 0
    loss_count: int = 0
    system_mode: str = "RESEARCH"
    metrics_json: Dict[str, Any] = field(default_factory=dict)
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class IntradaySnapshotRecord:
    """Immutable contract for intraday risk checkpoints (e.g. 09:30, 11:30, 13:30, 15:30)."""
    checkpoint_time: str
    current_equity: float
    cash_available: float
    margin_utilized: float
    unrealized_pnl: float
    realized_pnl: float
    open_positions_count: int
    drawdown_pct: float
    kill_line_triggered: bool = False
    system_mode: str = "RESEARCH"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class MarketStateSnapshotRecord:
    """Immutable contract for macro market state snapshots."""
    date: str
    nifty_price: float
    nifty_ema200: float
    vix: float
    atr: float
    market_state: str
    trend_regime: str
    volatility_regime: str
    breadth_pct: float
    mqi_score: Optional[float] = None
    mqi_level: Optional[str] = None
    no_trade_day: bool = False

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# ── 2. FINANCIAL PAYLOAD SANITIZATION & LOCAL JOURNALING ─────────────────────

def _sanitize_payload(data: Any) -> Any:
    """
    Recursively sanitize dictionaries/lists.
    Converts NaN, Inf, -Inf floats to None (SQL NULL) to prevent PostgreSQL numeric syntax errors.
    """
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, dict):
        return {k: _sanitize_payload(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_sanitize_payload(v) for v in data]
    return data


def _append_local_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """
    Durable local WAL journal. Preserves snapshot writes if Supabase is temporarily unreachable.
    """
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_LOCAL_JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"[db.snapshots] Failed to write local journal: {e}")


def replay_local_journal() -> int:
    """
    Automated WAL Journal Replay Protocol.
    Flushes buffered offline records from storage/snapshots_journal.jsonl to Supabase.
    Returns the number of successfully replayed records.
    """
    if not _LOCAL_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed_count = 0
    remaining_records = []

    try:
        with open(_LOCAL_JOURNAL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
                event_type = entry.get("event_type")
                payload = entry.get("payload", {})

                if event_type == "DAILY_PORTFOLIO_SNAPSHOT":
                    s_date = payload.get("snapshot_date")
                    s_mode = payload.get("system_mode", "RESEARCH")
                    if s_date:
                        cleaned = {k: v for k, v in payload.items() if k not in ("cash_balance", "margin_used", "daily_pnl")}
                        existing = sb.table("daily_portfolio_snapshot").select("id").eq("snapshot_date", s_date).eq("system_mode", s_mode).limit(1).execute()
                        if existing.data:
                            sb.table("daily_portfolio_snapshot").update(cleaned).eq("id", existing.data[0]["id"]).execute()
                        else:
                            sb.table("daily_portfolio_snapshot").insert(cleaned).execute()
                    replayed_count += 1
                elif event_type == "INTRADAY_PORTFOLIO_SNAPSHOT":
                    sb.table("intraday_portfolio_snapshot").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "MARKET_STATE_HISTORY":
                    d_val = payload.get("date")
                    if d_val:
                        res = sb.table("market_state_history").update(payload).eq("date", d_val).execute()
                        if not res.data:
                            sb.table("market_state_history").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "MQI_SCORE_UPDATE":
                    date_val = payload.get("date")
                    if date_val:
                        up_payload = {k: v for k, v in payload.items() if k != "date"}
                        sb.table("market_state_history").update(up_payload).eq("date", date_val).execute()
                        replayed_count += 1
                else:
                    remaining_records.append(line)
            except Exception as e:
                logger.warning(f"[db.snapshots] Replay item failed, keeping in WAL: {e}")
                remaining_records.append(line)

        # Update or truncate journal file
        if not remaining_records:
            _LOCAL_JOURNAL_FILE.unlink(missing_ok=True)
            logger.info(f"[db.snapshots] Replayed {replayed_count} buffered records from local WAL journal.")
        else:
            with open(_LOCAL_JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(remaining_records)
            logger.info(f"[db.snapshots] Replayed {replayed_count} records. {len(remaining_records)} remain buffered.")

    except Exception as e:
        logger.error(f"[db.snapshots] Error during local journal replay: {e}")

    return replayed_count


# ── 3. DAILY PORTFOLIO SNAPSHOTS ─────────────────────────────────────────────

def upsert_daily_snapshot(snapshot: Union[dict, PortfolioSnapshot]) -> dict:
    """
    Insert or update today's portfolio snapshot.
    One row per day (snapshot_date is UNIQUE).
    Called at EOD 3:35 PM by eod_routine().
    """
    from mjonai.core.time_utils import now_ist
    raw_dict = snapshot.to_dict() if isinstance(snapshot, PortfolioSnapshot) else snapshot
    if not isinstance(raw_dict, dict) or not raw_dict:
        logger.warning("[db.snapshots] upsert_daily_snapshot received empty payload.")
        return {}

    sanitized = _sanitize_payload(raw_dict)
    snapshot_date = str(sanitized.get("snapshot_date", ""))
    system_mode = str(sanitized.get("system_mode", "RESEARCH")).upper()

    if not snapshot_date:
        logger.error("[db.snapshots] upsert_daily_snapshot missing mandatory 'snapshot_date'.")
        return {}

    record = {
        **sanitized,
        "snapshot_date": snapshot_date,
        "system_mode": system_mode,
        "updated_at": now_ist().isoformat(),
    }

    try:
        def _execute_upsert():
            cleaned = {k: v for k, v in record.items() if k not in ("cash_balance", "margin_used", "daily_pnl")}
            existing = sb.table("daily_portfolio_snapshot").select("id").eq("snapshot_date", snapshot_date).eq("system_mode", system_mode).limit(1).execute()
            if existing.data:
                return sb.table("daily_portfolio_snapshot").update(cleaned).eq("id", existing.data[0]["id"]).execute()
            else:
                return sb.table("daily_portfolio_snapshot").insert(cleaned).execute()

        result = _execute_with_retry(_execute_upsert, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.snapshots] upsert_daily_snapshot failed: {e} -> Buffering to local journal.")
        _append_local_journal("DAILY_PORTFOLIO_SNAPSHOT", record)
        return record


def upsert_intraday_snapshot(snapshot: Union[dict, IntradaySnapshotRecord]) -> dict:
    """
    Insert an intraday risk checkpoint (e.g. 09:30, 11:30, 13:30, 15:30).
    Provides crash recovery and live intraday drawdown attribution.
    """
    from mjonai.core.time_utils import now_ist
    raw_dict = snapshot.to_dict() if isinstance(snapshot, IntradaySnapshotRecord) else snapshot
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    checkpoint_time = str(sanitized.get("checkpoint_time", now_ist().isoformat()))
    system_mode = str(sanitized.get("system_mode", "RESEARCH")).upper()

    record = {
        **sanitized,
        "checkpoint_time": checkpoint_time,
        "system_mode": system_mode,
    }

    try:
        def _execute_insert():
            return sb.table("intraday_portfolio_snapshot").insert(record).execute()

        result = _execute_with_retry(_execute_insert, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.snapshots] upsert_intraday_snapshot failed: {e} -> Buffering to local journal.")
        _append_local_journal("INTRADAY_PORTFOLIO_SNAPSHOT", record)
        return record


def get_snapshot_history(days: int = 30, system_mode: str = "RESEARCH") -> list:
    """
    Return last N days of portfolio snapshots.
    Used by QuantStats for Sharpe, Sortino, equity curve.
    Strictly filters by system_mode to guarantee environment isolation.
    """
    from mjonai.core.time_utils import now_ist
    try:
        since = (now_ist() - timedelta(days=days)).strftime("%Y-%m-%d")

        def _execute_query():
            return (
                sb.table("daily_portfolio_snapshot")
                .select("*")
                .eq("system_mode", system_mode.upper())
                .gte("snapshot_date", since)
                .order("snapshot_date", desc=False)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.snapshots] get_snapshot_history failed: {e}")
        return []


def get_latest_snapshot_before(system_mode: str, before_date_iso: str) -> Optional[dict]:
    """
    Most recent snapshot STRICTLY BEFORE the given date (ISO yyyy-mm-dd).

    EOD settlement must chain from yesterday's row — reading today's own
    snapshot and adding realized P&L again double-counts on every re-run.
    """
    try:
        def _execute_query():
            return (
                sb.table("daily_portfolio_snapshot")
                .select("*")
                .eq("system_mode", system_mode.upper())
                .lt("snapshot_date", before_date_iso)
                .order("snapshot_date", desc=True)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.snapshots] get_latest_snapshot_before failed: {e}")
        return None


def get_latest_snapshot(system_mode: str = "RESEARCH") -> Optional[dict]:
    """
    Return the most recent portfolio snapshot for the given system_mode.
    Used by dashboard and eod_routine().
    """
    try:
        def _execute_query():
            return (
                sb.table("daily_portfolio_snapshot")
                .select("*")
                .eq("system_mode", system_mode.upper())
                .order("snapshot_date", desc=True)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.snapshots] get_latest_snapshot failed: {e}")
        return None


# ── 4. MARKET STATE HISTORY ──────────────────────────────────────────────────

_MARKET_STATE_COLUMNS = {
    "id", "date", "nifty_price", "ema200", "price_structure", "breadth_pct",
    "breadth_score", "vix", "vix_score", "fii_net_cr", "fii_score", "total_score",
    "market_state", "mqi_score", "mqi_level", "no_trade_day", "high_vol_override",
    "data_quality", "ema20", "session_phase", "created_at", "updated_at", "is_deleted"
}


def upsert_market_state(record: Union[dict, MarketStateSnapshotRecord]) -> dict:
    """
    Insert or update today's market state record with explicit conflict resolution.
    """
    from mjonai.core.time_utils import now_ist
    raw_dict = record.to_dict() if isinstance(record, MarketStateSnapshotRecord) else record
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    date_str = str(sanitized.get("date", ""))
    if not date_str:
        logger.error("[db.snapshots] upsert_market_state missing mandatory 'date' field.")
        return {}

    if "nifty_ema200" in sanitized and "ema200" not in sanitized:
        sanitized["ema200"] = sanitized["nifty_ema200"]

    filtered = {k: v for k, v in sanitized.items() if k in _MARKET_STATE_COLUMNS}
    filtered["updated_at"] = now_ist().isoformat()

    try:
        def _execute_upsert():
            res = sb.table("market_state_history").update(filtered).eq("date", date_str).execute()
            if res and res.data:
                return res
            return sb.table("market_state_history").insert(filtered).execute()

        result = _execute_with_retry(_execute_upsert, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else filtered
    except Exception as e:
        logger.error(f"[db.snapshots] upsert_market_state failed: {e} -> Buffering to local journal.")
        _append_local_journal("MARKET_STATE_HISTORY", filtered)
        return filtered


def update_mqi_score(date_str: str, mqi_score: float, mqi_level: str, no_trade_day: bool) -> bool:
    """
    Update MQI fields on today's market state record.
    Upserts row if it does not exist yet.
    """
    sanitized_score = _sanitize_payload(mqi_score)
    payload = {
        "date": date_str,
        "mqi_score": sanitized_score,
        "mqi_level": mqi_level,
        "no_trade_day": no_trade_day,
    }

    try:
        def _execute_update_or_insert():
            res = (
                sb.table("market_state_history")
                .update(payload)
                .eq("date", date_str)
                .execute()
            )
            if res and res.data:
                return res
            return sb.table("market_state_history").insert(payload).execute()

        result = _execute_with_retry(_execute_update_or_insert, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.snapshots] update_mqi_score failed: {e}")
        _append_local_journal("MQI_SCORE_UPDATE", {"date": date_str, **payload})
        return False


def get_latest_market_state() -> Optional[dict]:
    """
    Return the most recent market state record.
    Orders strictly by (date desc, created_at desc) to eliminate semantic race conditions.
    """
    try:
        def _execute_query():
            return (
                sb.table("market_state_history")
                .select("*")
                .order("date", desc=True)
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.snapshots] get_latest_market_state failed: {e} — returning None")
        return None


# ── 5. 3-TIER PEAK EQUITY WATERMARK & REAL-TIME DRAWDOWN ENGINE ──────────────

def reset_peak_equity_cache() -> None:
    """Clear in-memory peak equity cache (used for session rollover and test isolation)."""
    global _CACHED_PEAK_EQUITY
    _CACHED_PEAK_EQUITY = None


def save_peak_equity(candidate_peak: float) -> float:
    """
    Save peak equity with mathematical monotonicity protection.
    Peak equity can NEVER decrease: new_peak = max(previous_peak, candidate_peak).
    Persists to:
      1. In-memory cache.
      2. Local durable state file (storage/peak_equity.json).
      3. Supabase system_log audit table.
    """
    global _CACHED_PEAK_EQUITY
    candidate = candidate_peak if not math.isnan(candidate_peak) else 0.0

    # Retrieve current baseline
    current_peak = _CACHED_PEAK_EQUITY
    if current_peak is None:
        current_peak = load_peak_equity(default=candidate)

    # Monotonicity rule: Never decrease
    enforced_peak = max(current_peak, candidate)
    _CACHED_PEAK_EQUITY = enforced_peak

    # Tier 2: Persist to local durable file
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        with open(_PEAK_EQUITY_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "peak_equity": enforced_peak,
                "updated_at_utc": datetime.now(timezone.utc).isoformat(),
            }, f)
    except Exception as e:
        logger.error(f"[db.snapshots] Failed to persist local peak equity file: {e}")

    # Tier 3: Persist audit log to Supabase
    try:
        sb.table("system_log").insert({
            "event_type": "PEAK_EQUITY",
            "message": str(round(enforced_peak, 2)),
            "level": "INFO",
        }).execute()
    except Exception as e:
        logger.warning(f"[db.snapshots] Supabase peak equity log write failed: {e}")

    return enforced_peak


def load_peak_equity(default: float) -> float:
    """
    Load peak equity watermark with 3-tier durable fallback:
      Tier 1: Query Supabase system_log.
      Tier 2: Load local durable storage (storage/peak_equity.json).
      Tier 3: Fall back to default capital baseline.
    Enforces monotonicity protection.
    """
    global _CACHED_PEAK_EQUITY
    recovered_peak: Optional[float] = None

    # Tier 1: Try Supabase
    try:
        def _execute_query():
            return (
                sb.table("system_log")
                .select("message")
                .eq("event_type", "PEAK_EQUITY")
                .order("created_at", desc=True)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        if data:
            recovered_peak = float(data[0]["message"])
    except Exception as e:
        logger.debug(f"[db.snapshots] Supabase peak equity query skipped/failed: {e}")

    # Tier 2: Try Local Durable File
    if recovered_peak is None and _PEAK_EQUITY_FILE.exists():
        try:
            with open(_PEAK_EQUITY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                if "peak_equity" in data:
                    recovered_peak = float(data["peak_equity"])
                    logger.info(f"[db.snapshots] Recovered peak equity {recovered_peak:,.2f} from local storage.")
        except Exception as e:
            logger.error(f"[db.snapshots] Failed reading local peak equity file: {e}")

    # Tier 3: Default Baseline
    final_peak = recovered_peak if recovered_peak is not None else default
    _CACHED_PEAK_EQUITY = final_peak
    return final_peak


def get_current_drawdown_pct(current_equity: float, default_capital: float = 200000.0) -> float:
    """
    Calculate real-time drawdown percentage relative to peak equity watermark.
    Formula: Drawdown % = ((Peak Equity - Current Equity) / Peak Equity) * 100
    Returns 0.0 if current_equity >= Peak Equity.
    Directly feeds 15% Kill Line circuit breaker.
    """
    if current_equity <= 0.0:
        return 100.0

    peak = load_peak_equity(default=default_capital)
    if peak <= 0.0:
        return 0.0

    if current_equity >= peak:
        # Save new high watermark automatically
        save_peak_equity(current_equity)
        return 0.0

    drawdown = ((peak - current_equity) / peak) * 100.0
    return round(drawdown, 2)
