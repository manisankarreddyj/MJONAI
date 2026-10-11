"""
Module: db/signals.py

Purpose: Quantitative Signal Intelligence Logging, Trade Outcome Attribution,
         Multi-Horizon Forward Returns Engine, and Alphalens Factor Analysis Pipeline.

Architectural Principles:
  1. Complete Signal Lifecycle Tracking (Birth -> Execution Link -> Outcome -> Alphalens Factor IC).
  2. High-Throughput Vector Ingestion (insert_signals_bulk for universe-wide scanners).
  3. Financial Float Sanitization (NaN/Inf -> None conversion to prevent PostgreSQL syntax errors).
  4. Resilient Database Persistence with Exponential Backoff Retries (_execute_with_retry).
  5. Type-Safe Immutable Data Contract (SignalIntelligenceRecord).
  6. Server-Side Range Queries for sub-millisecond daily scans.
  7. 100% Backwards-Compatible Public API for all dependent callers.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timezone
import json
import logging
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union
import uuid

from mjonai.db.client import sb, is_db_connected, execute_with_retry as _execute_with_retry

logger = logging.getLogger(__name__)

_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"  # repo root (ADR-0008)
_SIGNALS_JOURNAL_FILE = _STORAGE_DIR / "signals_journal.jsonl"


# ── 1. TYPE-SAFE IMMUTABLE SIGNAL DATA CONTRACT ──────────────────────────────

@dataclass(frozen=True)
class SignalIntelligenceRecord:
    """
    Immutable representation of a quantitative signal at the moment of generation.
    Captures complete market microstructure and quantitative factor state.
    """
    symbol: str
    signal_type: str                   # "BUY" | "SELL" | "HOLD"
    strategy_id: str                   # "ORB_15M" | "SUPERTREND_VOL" | "MEAN_REVERSION"
    raw_signal_value: float            # Raw mathematical indicator value
    final_confidence: float            # 0.0 to 1.0 confidence score
    planned_quantity: int
    entry_price: Optional[float] = None
    sl_price: Optional[float] = None
    target_price: Optional[float] = None
    timeframe: str = "15m"
    market_regime: Optional[str] = None
    mqi_score: Optional[float] = None
    generated_at: Optional[str] = None
    metadata_json: Dict[str, Any] = field(default_factory=dict)
    # Outcome attribution fields
    actual_outcome: Optional[str] = None      # "WIN" | "LOSS" | "BREAKEVEN"
    actual_rr: Optional[float] = None
    actual_pnl_gross: Optional[float] = None
    actual_pnl_net: Optional[float] = None
    holding_days: Optional[int] = None
    exit_reason: Optional[str] = None
    # Alphalens forward returns
    forward_return_1d: Optional[float] = None
    forward_return_5d: Optional[float] = None
    forward_return_10d: Optional[float] = None
    forward_return_20d: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to clean dictionary omitting None fields."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# ── 2. FINANCIAL PAYLOAD SANITIZATION ────────────────────────────────────────

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


def _append_signal_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """Persist an unrecoverable primary-signal write for a later replay."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        entry = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_SIGNALS_JOURNAL_FILE, "a", encoding="utf-8") as handle:
            handle.write(json.dumps(entry) + "\n")
    except Exception as exc:
        logger.error(f"[db.signals] Failed to write local journal: {exc}")


def replay_signal_journal() -> int:
    """Replay buffered primary-signal writes after database connectivity returns."""
    if not _SIGNALS_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed = 0
    remaining: List[str] = []
    try:
        with open(_SIGNALS_JOURNAL_FILE, "r", encoding="utf-8") as handle:
            lines = handle.readlines()
        for line in lines:
            try:
                entry = json.loads(line)
                event_type = entry.get("event_type")
                payload = entry.get("payload") or {}
                if event_type == "INSERT_SIGNAL":
                    clean_record = _prepare_signal_record(payload)
                    sb.table("signal_intelligence_log").upsert(clean_record, on_conflict="id").execute()
                elif event_type == "UPDATE_SIGNAL_OUTCOME":
                    signal_id = payload.pop("id", None)
                    if not signal_id:
                        raise ValueError("missing signal id")
                    clean_payload = {k: v for k, v in _sanitize_payload(payload).items() if k in _KNOWN_SIGNAL_COLUMNS}
                    sb.table("signal_intelligence_log").update(clean_payload).eq("id", signal_id).execute()
                else:
                    raise ValueError(f"unsupported journal event: {event_type}")
                replayed += 1
            except Exception as exc:
                logger.warning(f"[db.signals] Replay item failed, keeping in WAL: {exc}")
                remaining.append(line)

        if remaining:
            with open(_SIGNALS_JOURNAL_FILE, "w", encoding="utf-8") as handle:
                handle.writelines(remaining)
        else:
            _SIGNALS_JOURNAL_FILE.unlink(missing_ok=True)
    except Exception as exc:
        logger.error(f"[db.signals] Error during signal WAL replay: {exc}")
    return replayed


# ── 3. LEGACY SIGNALS (DEPRECATED COMPATIBILITY) ─────────────────────────────

def insert_signal(signal: dict) -> dict:
    """Insert a new signal record into legacy signals table. Returns inserted row."""
    if not isinstance(signal, dict) or not signal:
        return {}
    sanitized = _sanitize_payload(signal)
    try:
        def _execute():
            return sb.table("signals").insert(sanitized).execute()
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else sanitized
    except Exception as e:
        logger.error(f"[db.signals] insert_signal failed: {e}")
        return sanitized


def get_signals_today() -> list:
    """Return all legacy signals generated today (IST date) with server-side filtering."""
    from mjonai.core.time_utils import today_ist
    today = str(today_ist())
    try:
        def _execute():
            return (
                sb.table("signals")
                .select("*")
                .gte("created_at", f"{today}T00:00:00+05:30")
                .lte("created_at", f"{today}T23:59:59+05:30")
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.signals] get_signals_today failed: {e}")
        return []


# ── 4. PRIMARY SIGNAL INTELLIGENCE LOG ───────────────────────────────────────

# Known columns in Supabase signal_intelligence_log table (verified against live schema)
_KNOWN_SIGNAL_COLUMNS = {
    "id", "created_at", "updated_at", "is_deleted", "strategy_id", "strategy_version",
    "symbol", "sector", "signal_type", "system_mode", "generated_at", "market_open_minutes",
    "time_of_day_bucket", "day_of_week", "week_of_month", "market_state", "mqi_level",
    "mqi_score", "vix_at_signal", "vix_rank", "nifty_level", "nifty_vs_ema200_pct",
    "breadth_pct", "fii_flow_cr", "macro_flags", "technical_score", "rsi_value",
    "rsi_score", "macd_score", "ema_score", "supertrend_score", "candle_score",
    "candle_pattern", "mtf_score", "volatility_score", "liquidity_score", "context_score",
    "final_confidence", "entry_price", "stop_loss", "target", "sl_method", "swing_low_used",
    "atr_at_signal", "sl_distance_pct", "target_distance_pct", "planned_rr", "real_rr_planned",
    "planned_quantity", "planned_capital", "planned_risk_amount", "position_size_pct",
    "devil_gap_risk", "devil_liquidity", "devil_data_quality", "devil_pattern_memory",
    "devil_correlation", "devil_real_rr", "devil_portfolio_limits", "devil_event_risk",
    "devil_all_passed", "devil_failure_reason", "devil_checks_mode", "earnings_safe",
    "earnings_days_away", "sector_cap_ok", "duplicate_symbol", "event_risk_flag",
    "bull_verdict", "bull_confidence", "bull_key_reasons", "bull_concerns", "bull_model_used",
    "bull_fallback_used", "supervisor_decision", "supervisor_reason", "supervisor_deciding_factor",
    "supervisor_model_used", "was_executed", "trade_id", "expiry_reason", "actual_outcome",
    "actual_rr", "actual_pnl_gross", "actual_pnl_net", "holding_days", "exit_reason",
    "forward_return_1d", "forward_return_3d", "forward_return_5d", "forward_return_10d",
    "forward_return_20d", "pnl_1d", "pnl_3d", "pnl_5d", "pnl_10d", "pnl_20d",
    "raw_signal_value", "signal_direction", "market_regime", "metadata_json", "sl_price",
    "target_price", "timeframe",
}


def _prepare_signal_record(raw_dict: dict) -> dict:
    """Filter raw signal dict to known columns, storing unmapped fields into metadata_json."""
    from mjonai.core.time_utils import now_ist
    sanitized = _sanitize_payload(raw_dict)
    known = {}
    extra = dict(sanitized.get("metadata_json") or {})

    for k, v in sanitized.items():
        if k in _KNOWN_SIGNAL_COLUMNS:
            known[k] = v
        else:
            extra[k] = v

    if extra:
        known["metadata_json"] = extra

    if "updated_at" not in known:
        known["updated_at"] = now_ist().isoformat()
    if "generated_at" not in known:
        known["generated_at"] = now_ist().isoformat()
    if not known.get("id"):
        known["id"] = str(uuid.uuid4())

    return known


def insert_signal_intelligence(signal: Union[dict, SignalIntelligenceRecord]) -> dict:
    """
    Insert a complete signal record into signal_intelligence_log.
    Primary signal table for quantitative trade execution and research.
    """
    raw_dict = signal.to_dict() if isinstance(signal, SignalIntelligenceRecord) else signal
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    record = _prepare_signal_record(raw_dict)

    try:
        def _execute():
            return sb.table("signal_intelligence_log").insert(record).execute()
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.signals] insert_signal_intelligence failed: {e} -> Buffering to WAL.")
        _append_signal_journal("INSERT_SIGNAL", record)
        return record


def insert_signals_bulk(signals: Sequence[Union[dict, SignalIntelligenceRecord]]) -> List[dict]:
    """
    High-throughput batch insertion for universe scanners.
    Reduces N network roundtrips into a single vectorized query.
    """
    from mjonai.core.time_utils import now_ist
    if not signals:
        return []

    now_str = now_ist().isoformat()
    sanitized_records = []

    for s in signals:
        raw_dict = s.to_dict() if isinstance(s, SignalIntelligenceRecord) else s
        if isinstance(raw_dict, dict) and raw_dict:
            clean = _prepare_signal_record(raw_dict)
            sanitized_records.append(clean)

    if not sanitized_records:
        return []

    try:
        def _execute():
            return sb.table("signal_intelligence_log").insert(sanitized_records).execute()
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or sanitized_records
    except Exception as e:
        logger.error(f"[db.signals] insert_signals_bulk failed for {len(sanitized_records)} items: {e} -> Buffering to WAL.")
        for record in sanitized_records:
            _append_signal_journal("INSERT_SIGNAL", record)
        return sanitized_records


def update_signal_outcome(
    signal_id: str,
    actual_outcome: str,
    actual_rr: Optional[float] = None,
    actual_pnl_gross: Optional[float] = None,
    actual_pnl_net: Optional[float] = None,
    holding_days: Optional[int] = None,
    exit_reason: Optional[str] = None,
) -> bool:
    """
    Update signal record with trade outcome when trade closes.
    Called on every trade close for mathematical outcome attribution.
    """
    if not signal_id:
        return False
    from mjonai.core.time_utils import now_ist

    payload: Dict[str, Any] = {
        "actual_outcome": actual_outcome,
        "actual_rr": round(actual_rr, 4) if actual_rr is not None and not math.isnan(actual_rr) else None,
        "actual_pnl_gross": round(actual_pnl_gross, 2) if actual_pnl_gross is not None and not math.isnan(actual_pnl_gross) else None,
        "actual_pnl_net": round(actual_pnl_net, 2) if actual_pnl_net is not None and not math.isnan(actual_pnl_net) else None,
        "holding_days": holding_days,
        "exit_reason": exit_reason,
        "updated_at": now_ist().isoformat(),
    }
    sanitized = _sanitize_payload(payload)

    try:
        def _execute():
            return (
                sb.table("signal_intelligence_log")
                .update(sanitized)
                .eq("id", signal_id)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.signals] update_signal_outcome failed for {signal_id}: {e} -> Buffering to WAL.")
        _append_signal_journal("UPDATE_SIGNAL_OUTCOME", {"id": signal_id, **sanitized})
        return False


def get_signals_intelligence_today(strategy_id: Optional[str] = None) -> list:
    """
    Return all signal_intelligence_log records created today (IST).
    Used by execution scanners to enforce daily signal limits per strategy.
    """
    from mjonai.core.time_utils import today_ist
    today = str(today_ist())
    try:
        def _execute():
            query = (
                sb.table("signal_intelligence_log")
                .select("id,signal_type,generated_at,symbol,strategy_id,final_confidence,planned_quantity")
                .gte("generated_at", f"{today}T00:00:00+05:30")
                .lte("generated_at", f"{today}T23:59:59+05:30")
            )
            if strategy_id:
                query = query.eq("strategy_id", strategy_id)
            return query.execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.signals] get_signals_intelligence_today failed: {e}")
        return []


def get_signal_by_id(signal_id: str) -> Optional[dict]:
    """
    Return a single signal record by UUID.
    Used when linking trade outcome back to signal.
    """
    if not signal_id:
        return None
    try:
        def _execute():
            return (
                sb.table("signal_intelligence_log")
                .select("*")
                .eq("id", signal_id)
                .limit(1)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.signals] get_signal_by_id failed for {signal_id}: {e}")
        return None


# ── 5. ALPHALENS FORWARD RETURNS ENGINE ──────────────────────────────────────

def get_signals_needing_forward_returns(limit: int = 1000) -> list:
    """
    Get all signals that don't have forward returns calculated yet.
    Returns signals with generated_at but no forward_return_1d.
    Called daily at 16:00 PM for automated factor performance attribution.
    """
    try:
        def _execute():
            return (
                sb.table("signal_intelligence_log")
                .select("id, symbol, generated_at, planned_quantity, raw_signal_value, final_confidence, strategy_id, entry_price")
                .is_("forward_return_1d", "null")
                .not_.is_("generated_at", "null")
                .limit(limit)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.signals] get_signals_needing_forward_returns failed: {e}")
        return []


def update_signal_forward_returns(signal_id: str, returns: dict) -> bool:
    """
    Update a signal's forward return values (1d, 5d, 10d, 20d) with float sanitization.
    """
    if not signal_id or not isinstance(returns, dict):
        return False
    from mjonai.core.time_utils import now_ist
    sanitized = _sanitize_payload(returns)
    sanitized["updated_at"] = now_ist().isoformat()

    try:
        def _execute():
            return (
                sb.table("signal_intelligence_log")
                .update(sanitized)
                .eq("id", signal_id)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.signals] update_signal_forward_returns failed for {signal_id}: {e}")
        return False


def get_signals_for_alphalens(
    strategy_id: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    limit: int = 5000
) -> list:
    """
    Get signals for Alphalens factor analysis tear-sheet generation.
    Only returns signals that have forward returns calculated.
    """
    try:
        def _execute():
            query = (
                sb.table("signal_intelligence_log")
                .select(
                    "id, symbol, generated_at, strategy_id, "
                    "signal_direction, market_state, "
                    "raw_signal_value, final_confidence, "
                    "forward_return_1d, forward_return_5d, "
                    "forward_return_10d, forward_return_20d"
                )
                .not_.is_("forward_return_1d", "null")
            )

            if strategy_id:
                query = query.eq("strategy_id", strategy_id)
            if start_date:
                query = query.gte("generated_at", f"{start_date}T00:00:00+05:30")
            if end_date:
                query = query.lte("generated_at", f"{end_date}T23:59:59+05:30")

            return query.limit(limit).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.signals] get_signals_for_alphalens failed: {e}")
        return []


def get_signals_intelligence_recent(
    days: int = 7,
    limit: int = 50,
    system_mode: Optional[str] = None,
) -> list:
    """
    Recent signals WITH their real debate columns (bull verdict/reasoning, supervisor
    decision) for the honest AI-boardroom transcript. Unlike get_signals_intelligence_today
    (which selects only daily-limit columns), this selects the reasoning fields so viewers
    render the ACTUAL agent output rather than fabricated defaults. Newest first.
    """
    from mjonai.core.time_utils import now_ist
    from datetime import timedelta
    try:
        since = (now_ist() - timedelta(days=max(1, days))).isoformat()

        def _execute():
            query = (
                sb.table("signal_intelligence_log")
                .select(
                    "id, symbol, strategy_id, signal_direction, final_confidence, "
                    "supervisor_decision, supervisor_reason, bull_verdict, bull_confidence, "
                    "bull_key_reasons, bull_concerns, bull_model_used, was_executed, generated_at"
                )
                .gte("generated_at", since)
                .order("generated_at", desc=True)
            )
            if system_mode:
                query = query.eq("system_mode", system_mode)
            return query.limit(max(1, limit)).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.signals] get_signals_intelligence_recent failed: {e}")
        return []


def get_forward_returns_by_signal_ids(signal_ids: Sequence[str], group_size: int = 50) -> Dict[str, Dict[str, Any]]:
    """
    Fetch forward returns + direction + regime tags for a set of signal ids.

    Chunks the id list (PostgREST URL-length safety) and maps results by
    signal id. Used by the learning loop to align realized forward returns
    with the calibration signal set — the input for real rank-IC.
    Fails closed to {} on any error (calibration then runs Brier-only, the
    honest no-data case).
    """
    ids = [str(s) for s in signal_ids if s]
    if not ids:
        return {}

    def _fetch_chunk(chunk: List[str]) -> list:
        def _execute():
            return (
                sb.table("signal_intelligence_log")
                .select(
                    "id, signal_direction, market_state, "
                    "forward_return_1d, forward_return_5d, "
                    "forward_return_10d, forward_return_20d"
                )
                .in_("id", chunk)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []

    try:
        by_id: Dict[str, Dict[str, Any]] = {}
        for i in range(0, len(ids), group_size):
            for row in _fetch_chunk(ids[i:i + group_size]):
                row_id = str(row.get("id"))
                if row_id:
                    by_id[row_id] = row
        return by_id
    except Exception as e:
        logger.error(f"[db.signals] get_forward_returns_by_signal_ids failed: {e}")
        return {}
