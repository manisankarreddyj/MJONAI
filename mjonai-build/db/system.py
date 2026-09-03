"""
Module: db/system.py

Purpose: Mission Control Telemetry, Scan Funnel Tracking, Infrastructure Health Probes,
         Strategy Performance Attribution Curves, Dynamic Agent Weight Governance,
         Immutable Risk Audit Events, and Offline WAL Journal Replay.

Architectural Principles:
  1. Multi-Timeframe & Multi-Asset Scan Funnel Tracking (1m, 5m, 15m, 1d | Equities, Options, MCX).
  2. Sub-Millisecond Infrastructure Health Probes (CPU %, RAM %, WebSocket status, API latencies).
  3. Risk-Adjusted Strategy Performance Rollups (Sharpe, Calmar, Profit Factor, Max Drawdown).
  4. Environment-Isolated Dynamic AI Agent Weight Recalibration (LIVE, PAPER, RESEARCH).
  5. Immutable Black-Box Risk Event Auditing (15% Kill line triggers, circuit breakers).
  6. Financial Float Sanitization (NaN/Inf -> None conversion preventing PostgreSQL syntax aborts).
  7. Resilient Database Persistence with Exponential Backoff Retries (_execute_with_retry).
  8. Offline Durable WAL Journaling & Automated Replay (replay_system_journal).
  9. Type-Safe Immutable Data Contracts (ScanLogRecord, SystemHealthRecord, StrategyPerformanceRecord, AgentWeightRecord).
 10. 100% Backwards-Compatible Public API for all callers.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from db.client import sb, is_db_connected, execute_with_retry as _execute_with_retry

logger = logging.getLogger(__name__)

# Local durable journal directory
_STORAGE_DIR = Path(__file__).resolve().parent.parent / "storage"
_SYSTEM_JOURNAL_FILE = _STORAGE_DIR / "system_journal.jsonl"


# ── 1. TYPE-SAFE IMMUTABLE DATA CONTRACTS ────────────────────────────────────

@dataclass(frozen=True)
class ScanLogRecord:
    """Immutable representation of a market scan cycle."""
    symbols_scanned: int
    signals_generated: int
    signals_approved: int
    scan_duration_ms: float
    timeframe: str = "15m"
    asset_class: str = "EQUITY"
    system_mode: str = "RESEARCH"
    passed_liquidity: int = 0
    passed_earnings: int = 0
    passed_breadth: int = 0
    passed_pattern_memory: int = 0
    scanned_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to clean dictionary omitting None fields."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class SystemHealthRecord:
    """Immutable representation of infrastructure telemetry."""
    oracle_cpu_pct: float
    oracle_ram_pct: float
    oracle_disk_pct: float
    websocket_healthy: bool
    internet_ok: bool
    groq_latency_ms: Optional[float] = None
    gemini_latency_ms: Optional[float] = None
    supabase_latency_ms: Optional[float] = None
    angelone_latency_ms: Optional[float] = None
    system_mode: str = "RESEARCH"
    logged_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class StrategyPerformanceRecord:
    """Immutable representation of strategy performance curves."""
    strategy_id: str
    strategy_version: str
    period_start: str
    period_end: str
    market_state: str = "ALL"
    mqi_level: str = "ALL"
    system_mode: str = "RESEARCH"
    total_trades: int = 0
    wins: int = 0
    losses: int = 0
    win_rate: Optional[float] = None
    profit_factor: Optional[float] = None
    sharpe_ratio: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    calmar_ratio: Optional[float] = None
    avg_rr: Optional[float] = None
    net_pnl: Optional[float] = None
    last_computed_at: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class AgentWeightRecord:
    """Immutable representation of dynamic AI agent weight recalibration."""
    agent_name: str
    old_weight: float
    new_weight: float
    weight_change: Optional[float] = None
    trigger_reason: str = "PERIODIC_EVALUATION"
    accuracy_pct: Optional[float] = None
    trades_evaluated: int = 0
    system_mode: str = "RESEARCH"
    recalibrated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# ── 2. DEFENSIVE SANITIZATION & CONVERTERS ───────────────────────────────────

def _sanitize_payload(data: Any) -> Any:
    """Recursively sanitize dictionaries/lists converting NaN/Inf floats to None."""
    if isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
        return data
    elif isinstance(data, dict):
        return {k: _sanitize_payload(v) for k, v in data.items()}
    elif isinstance(data, (list, tuple)):
        return [_sanitize_payload(v) for v in data]
    return data


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert any JSON/database value to int."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert any JSON/database value to float."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        f = float(val)
        return default if math.isnan(f) or math.isinf(f) else f
    except (ValueError, TypeError):
        return default


def _safe_list(val: Any) -> List[Any]:
    """Safely convert any JSON/database value to a list."""
    if isinstance(val, (list, tuple)):
        return list(val)
    return []


# ── 3. LOCAL DURABLE WAL JOURNAL ─────────────────────────────────────────────

def _append_system_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """Durable local WAL journal for system events during network disconnects."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_SYSTEM_JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"[db.system] Failed to write local journal: {e}")


def replay_system_journal() -> int:
    """
    Automated WAL Journal Replay Protocol for System Telemetry.
    Flushes buffered offline records to Supabase.
    """
    if not _SYSTEM_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed_count = 0
    remaining_records = []

    try:
        with open(_SYSTEM_JOURNAL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
                event_type = entry.get("event_type")
                payload = entry.get("payload", {})

                if event_type == "INSERT_SCAN_LOG":
                    sb.table("scan_log").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "INSERT_HEALTH_LOG":
                    sb.table("system_health_log").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "INSERT_RISK_EVENT":
                    sb.table("risk_events").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "INSERT_SYSTEM_LOG":
                    sb.table("system_log").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "INSERT_WEIGHT_LOG":
                    sb.table("agent_weight_log").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "UPSERT_STRATEGY_PERFORMANCE":
                    on_conflict_cols = (
                        "strategy_id,strategy_version,"
                        "period_start,period_end,"
                        "market_state,mqi_level,system_mode"
                    )
                    sb.table("strategy_performance").upsert(payload, on_conflict=on_conflict_cols).execute()
                    replayed_count += 1
                else:
                    remaining_records.append(line)
            except Exception as e:
                logger.warning(f"[db.system] Replay item failed, keeping in WAL: {e}")
                remaining_records.append(line)

        if not remaining_records:
            _SYSTEM_JOURNAL_FILE.unlink(missing_ok=True)
            logger.info(f"[db.system] Replayed {replayed_count} buffered records from local WAL.")
        else:
            with open(_SYSTEM_JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(remaining_records)
    except Exception as e:
        logger.error(f"[db.system] Error during system WAL replay: {e}")

    return replayed_count


# ── 4. SCAN FUNNEL LOGGING ───────────────────────────────────────────────────

def insert_scan_log(log: Union[dict, ScanLogRecord]) -> dict:
    """
    Insert a scan cycle record after every market scan.
    Captures signal funnel counts, duration, timeframe, and asset class.
    """
    from core.time_utils import now_ist
    raw_dict = log.to_dict() if isinstance(log, ScanLogRecord) else log
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    record = {
        **sanitized,
        "scanned_at": sanitized.get("scanned_at", now_ist().isoformat()),
    }

    try:
        def _execute():
            return sb.table("scan_log").insert(record).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.system] insert_scan_log failed: {e} -> Buffering to WAL.")
        _append_system_journal("INSERT_SCAN_LOG", record)
        return record


def get_scan_history(
    hours: int = 24,
    timeframe: Optional[str] = None,
    system_mode: str = "RESEARCH",
) -> list:
    """
    Return scan_log records from last N hours with optional timeframe filtering.
    """
    from core.time_utils import now_ist
    sys_mode = system_mode.upper()

    try:
        since = (now_ist() - timedelta(hours=hours)).isoformat()

        def _execute_query():
            query = (
                sb.table("scan_log")
                .select("*")
                .gte("scanned_at", since)
                .order("scanned_at", desc=False)
            )
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        if timeframe:
            tf_clean = timeframe.strip().lower()
            data = [d for d in data if str(d.get("timeframe", "15m")).lower() == tf_clean]
        return data
    except Exception as e:
        logger.error(f"[db.system] get_scan_history failed: {e}")
        return []


# ── 5. SYSTEM HEALTH LOGGING & AGGREGATION ────────────────────────────────────

def insert_health_log(log: Union[dict, SystemHealthRecord]) -> dict:
    """
    Insert an infrastructure health snapshot.
    Tracks CPU, RAM, Disk, WebSocket status, and API latencies.
    """
    from core.time_utils import now_ist
    raw_dict = log.to_dict() if isinstance(log, SystemHealthRecord) else log
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    record = {
        **sanitized,
        "logged_at": sanitized.get("logged_at", now_ist().isoformat()),
    }

    try:
        def _execute():
            return sb.table("system_health_log").insert(record).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.system] insert_health_log failed: {e} -> Buffering to WAL.")
        _append_system_journal("INSERT_HEALTH_LOG", record)
        return record


def get_health_summary(hours: int = 24, system_mode: str = "RESEARCH") -> dict:
    """
    Return aggregated health telemetry for the last N hours.
    Used by dashboard health panels and /status alerts.
    """
    from core.time_utils import now_ist
    try:
        since = (now_ist() - timedelta(hours=hours)).isoformat()

        def _execute_query():
            return (
                sb.table("system_health_log")
                .select("*")
                .gte("logged_at", since)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []
        if not rows:
            return {"total_readings": 0, "hours_covered": hours}

        def _avg(key: str) -> Optional[float]:
            vals = [_safe_float(r.get(key)) for r in rows if r.get(key) is not None]
            return round(sum(vals) / len(vals), 1) if vals else None

        return {
            "total_readings": len(rows),
            "avg_cpu_pct": _avg("oracle_cpu_pct"),
            "avg_ram_pct": _avg("oracle_ram_pct"),
            "avg_disk_pct": _avg("oracle_disk_pct"),
            "avg_groq_latency_ms": _avg("groq_latency_ms"),
            "avg_gemini_latency_ms": _avg("gemini_latency_ms"),
            "avg_supabase_latency_ms": _avg("supabase_latency_ms"),
            "websocket_failures": sum(1 for r in rows if r.get("websocket_healthy") is False),
            "internet_failures": sum(1 for r in rows if r.get("internet_ok") is False),
            "hours_covered": hours,
        }
    except Exception as e:
        logger.error(f"[db.system] get_health_summary failed: {e}")
        return {"total_readings": 0, "hours_covered": hours}


# ── 6. STRATEGY PERFORMANCE ATTRIBUTION ──────────────────────────────────────

def upsert_strategy_performance(record: Union[dict, StrategyPerformanceRecord]) -> dict:
    """
    Insert or update a strategy performance rollup record.
    UNIQUE constraint: strategy_id + strategy_version + period_start + period_end + market_state + mqi_level + system_mode.
    """
    from core.time_utils import now_ist
    raw_dict = record.to_dict() if isinstance(record, StrategyPerformanceRecord) else record
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    now_str = now_ist().isoformat()
    rec = {
        **sanitized,
        "last_computed_at": sanitized.get("last_computed_at", now_str),
        "updated_at": now_str,
    }

    on_conflict_cols = (
        "strategy_id,strategy_version,"
        "period_start,period_end,"
        "market_state,mqi_level,system_mode"
    )

    try:
        def _execute():
            return sb.table("strategy_performance").upsert(rec, on_conflict=on_conflict_cols).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else rec
    except Exception as e:
        logger.error(f"[db.system] upsert_strategy_performance failed: {e} -> Buffering to WAL.")
        _append_system_journal("UPSERT_STRATEGY_PERFORMANCE", rec)
        return rec


def get_strategy_performance(
    strategy_id: Optional[str] = None,
    market_state: str = "ALL",
    system_mode: str = "RESEARCH",
) -> list:
    """
    Return strategy performance records for dashboard.
    Strictly filters by system_mode to prevent mixing research and live metrics.
    """
    sys_mode = system_mode.upper()
    try:
        def _execute_query():
            query = (
                sb.table("strategy_performance")
                .select("*")
                .eq("system_mode", sys_mode)
                .order("win_rate", desc=True)
            )
            if market_state != "ALL":
                query = query.eq("market_state", market_state)
            if strategy_id:
                query = query.eq("strategy_id", strategy_id)
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.system] get_strategy_performance failed: {e}")
        return []


# ── 7. AGENT WEIGHT GOVERNANCE ───────────────────────────────────────────────

def insert_weight_log(log: Union[dict, AgentWeightRecord]) -> dict:
    """
    Insert an agent dynamic weight recalibration event.
    Triggered periodically after performance evaluation.
    """
    from core.time_utils import now_ist
    raw_dict = log.to_dict() if isinstance(log, AgentWeightRecord) else log
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    old_w = _safe_float(sanitized.get("old_weight", 1.0), default=1.0)
    new_w = _safe_float(sanitized.get("new_weight", 1.0), default=1.0)
    w_change = round(new_w - old_w, 4)

    record = {
        **sanitized,
        "weight_change": sanitized.get("weight_change", w_change),
        "recalibrated_at": sanitized.get("recalibrated_at", now_ist().isoformat()),
    }

    try:
        def _execute():
            return sb.table("agent_weight_log").insert(record).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.system] insert_weight_log failed: {e} -> Buffering to WAL.")
        _append_system_journal("INSERT_WEIGHT_LOG", record)
        return record


def get_latest_weights(system_mode: str = "RESEARCH") -> Dict[str, float]:
    """
    Return most recent dynamic weight for each AI agent partitioned by system_mode.
    Safe default 1.0 for agents without calibration records.
    """
    sys_mode = system_mode.upper()
    default_agents = ["BULL", "BEAR", "DEVIL", "ECONOMIST", "SUPERVISOR"]
    weights: Dict[str, float] = {a: 1.0 for a in default_agents}

    try:
        def _execute_query():
            return (
                sb.table("agent_weight_log")
                .select("agent_name, new_weight, recalibrated_at")
                .eq("system_mode", sys_mode)
                .order("recalibrated_at", desc=True)
                .limit(100)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []
        for row in rows:
            agent = str(row.get("agent_name") or "").strip().upper()
            if agent and agent not in weights:
                weights[agent] = _safe_float(row.get("new_weight"), default=1.0)
            elif agent and weights.get(agent) == 1.0:
                weights[agent] = _safe_float(row.get("new_weight"), default=1.0)
        return weights
    except Exception as e:
        logger.error(f"[db.system] get_latest_weights failed: {e}")
        return weights


# ── 8. RISK EVENTS & IMMUTABLE SYSTEM AUDIT ──────────────────────────────────

def insert_risk_event(
    event_type: str,
    message: str,
    level: str = "WARNING",
    system_mode: str = "RESEARCH",
) -> bool:
    """
    Log an immutable risk event (Kill line triggers, circuit breakers, margin calls).
    """
    from core.time_utils import now_ist
    record = {
        "event_type": str(event_type),
        "message": str(message),
        "level": str(level).upper(),
        "system_mode": str(system_mode).upper(),
        "triggered_at": now_ist().isoformat(),
    }

    try:
        def _execute():
            return sb.table("risk_events").insert(record).execute()

        _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return True
    except Exception as e:
        logger.error(f"[db.system] insert_risk_event failed: {e} -> Buffering to WAL.")
        _append_system_journal("INSERT_RISK_EVENT", record)
        return False


def insert_system_log(
    event_type: str,
    message: str,
    level: str = "INFO",
    system_mode: str = "RESEARCH",
) -> bool:
    """
    Insert a system operational log entry (startups, shutdowns, cron runs).
    Resilient to schemas with or without level/system_mode columns.
    """
    from core.time_utils import now_ist
    record = {
        "event_type": str(event_type),
        "message": str(message),
        "level": str(level).upper(),
        "system_mode": str(system_mode).upper(),
        "created_at": now_ist().isoformat(),
    }

    try:
        def _execute():
            try:
                return sb.table("system_log").insert(record).execute()
            except Exception as inner_err:
                # If Supabase table does not have level/system_mode columns, fallback to minimal payload
                if "column" in str(inner_err).lower() or "pgrst204" in str(inner_err).lower() or "400" in str(inner_err):
                    minimal_record = {
                        "event_type": str(event_type),
                        "message": str(message),
                        "created_at": now_ist().isoformat(),
                    }
                    return sb.table("system_log").insert(minimal_record).execute()
                raise inner_err

        _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return True
    except Exception as e:
        logger.error(f"[db.system] insert_system_log failed: {e} -> Buffering to WAL.")
        _append_system_journal("INSERT_SYSTEM_LOG", record)
        return False

