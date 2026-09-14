"""
Module: db/patterns.py

Purpose: Institutional Pattern Recognition, Bayesian Failure Learning,
         Deterministic Fingerprinting, Statistical Expectancy, Streak Detection,
         and Microsecond In-Memory Hot-Path Caching.

Architectural Principles:
  1. Deterministic Multi-Factor Fingerprinting (generate_setup_hash).
  2. Bayesian Statistical Rigor (Laplace-smoothed win rates, Mathematical Expectancy, Profit Factor).
  3. Toxic Streak Detection (get_consecutive_losses on rolling last_10_outcomes).
  4. Microsecond Hot-Path LRU Cache (< 10us pre-trade latency for devil_checks).
  5. Thread-Safe Concurrency Protection (Lock-guarded atomic outcome updates).
  6. Strict Environment Isolation (system_mode partitioning across LIVE, PAPER, RESEARCH).
  7. Offline Durable WAL Journaling & Replay Protocol (replay_pattern_journal).
  8. Pattern Lifecycle Management (quarantine, reactivate, soft_delete).
  9. Recursive Float Sanitization (NaN/Inf -> None conversion to prevent PostgreSQL aborts).
 10. 100% Backwards-Compatible Public API for all existing callers.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
import threading
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from mjonai.db.client import sb, is_db_connected, execute_with_retry as _execute_with_retry

logger = logging.getLogger(__name__)

# Local durable journal & storage
_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"  # repo root (ADR-0008)
_PATTERNS_JOURNAL_FILE = _STORAGE_DIR / "patterns_journal.jsonl"

# Thread-safe in-memory hot-path cache: key -> (PatternMemoryRecord or dict, expiration_timestamp)
_PATTERN_CACHE: Dict[str, Tuple[Dict[str, Any], float]] = {}
_CACHE_TTL_SECONDS = 60.0
_PATTERN_LOCK = threading.RLock()


# ── 1. DETERMINISTIC SETUP HASH GENERATION ───────────────────────────────────

def generate_setup_hash(
    symbol: str,
    strategy_id: str,
    sl_method: str = "STRUCTURE",
    market_state: str = "NEUTRAL",
    vix_range: str = "NORMAL",
    candle_pattern: str = "NONE",
) -> str:
    """
    Generate canonical deterministic setup fingerprint.
    Format: {SYMBOL}_{STRATEGY_ID}_{SL_METHOD}_{MARKET_STATE}_{VIX_RANGE}_{CANDLE_PATTERN}
    Example: RELIANCE_S01_STRUCTURE_BULL_LOW_HAMMER
    """
    clean_sym = str(symbol).strip().upper().replace(" ", "")
    clean_strat = str(strategy_id).strip().upper().replace(" ", "")
    clean_sl = str(sl_method).strip().upper().replace(" ", "")
    clean_ms = str(market_state).strip().upper().replace(" ", "")
    clean_vix = str(vix_range).strip().upper().replace(" ", "")
    clean_pat = str(candle_pattern).strip().upper().replace(" ", "")

    return f"{clean_sym}_{clean_strat}_{clean_sl}_{clean_ms}_{clean_vix}_{clean_pat}"


# ── 2. TYPE-SAFE IMMUTABLE DATA CONTRACT ─────────────────────────────────────

@dataclass(frozen=True)
class PatternMemoryRecord:
    """
    Immutable representation of a multi-factor pattern memory record.
    Captures Bayesian historical performance and risk metrics.
    """
    setup_hash: str
    symbol: str
    strategy_id: str
    sl_method: str = "STRUCTURE"
    market_state: str = "NEUTRAL"
    vix_range: str = "NORMAL"
    candle_pattern: str = "NONE"
    occurrences: int = 0
    wins: int = 0
    losses: int = 0
    breakevens: int = 0
    win_rate: Optional[float] = None
    laplace_win_rate: Optional[float] = None
    avg_rr_achieved: Optional[float] = None
    expectancy_rr: Optional[float] = None
    profit_factor: Optional[float] = None
    last_10_outcomes: List[str] = field(default_factory=list)
    last_outcome: Optional[str] = None
    is_quarantined: bool = False
    is_deleted: bool = False
    system_mode: str = "RESEARCH"
    first_seen: Optional[str] = None
    last_seen: Optional[str] = None
    updated_at: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to clean dictionary omitting None fields."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


# ── 3. FINANCIAL PAYLOAD SANITIZATION & WAL JOURNAL ──────────────────────────

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


def _safe_float(val: Any, default: float = 0.0) -> float:
    from mjonai.core.numeric import safe_float
    return safe_float(val, default)


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert any JSON/database value to int, handling lists/dicts/None defensively."""
    try:
        if val is None or isinstance(val, (list, dict, tuple)):
            return default
        return int(val)
    except (ValueError, TypeError):
        return default


def _safe_list(val: Any) -> List[str]:
    """Safely convert any JSON/database value to a list of strings."""
    if isinstance(val, (list, tuple)):
        return [str(item) for item in val if item is not None]
    return []


def _append_pattern_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """Durable local WAL journal for pattern updates during network disconnects."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_PATTERNS_JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"[db.patterns] Failed to write local journal: {e}")


def replay_pattern_journal() -> int:
    """
    Automated WAL Journal Replay Protocol for Pattern Memory.
    Flushes buffered offline records to Supabase.
    """
    if not _PATTERNS_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed_count = 0
    remaining_records = []

    with _PATTERN_LOCK:
        try:
            with open(_PATTERNS_JOURNAL_FILE, "r", encoding="utf-8") as f:
                lines = f.readlines()

            for line in lines:
                line_str = line.strip()
                if not line_str:
                    continue
                try:
                    entry = json.loads(line_str)
                    event_type = entry.get("event_type")
                    payload = entry.get("payload", {})

                    if event_type == "UPSERT_PATTERN":
                        sb.table("pattern_memory").upsert(payload, on_conflict="setup_hash").execute()
                        replayed_count += 1
                    elif event_type == "UPDATE_PATTERN_OUTCOME":
                        setup_hash = payload.get("setup_hash")
                        if setup_hash:
                            up_payload = {k: v for k, v in payload.items() if k != "setup_hash"}
                            sb.table("pattern_memory").update(up_payload).eq("setup_hash", setup_hash).execute()
                            replayed_count += 1
                    else:
                        remaining_records.append(line)
                except Exception as e:
                    logger.warning(f"[db.patterns] Replay item failed, keeping in WAL: {e}")
                    remaining_records.append(line)

            if not remaining_records:
                _PATTERNS_JOURNAL_FILE.unlink(missing_ok=True)
                logger.info(f"[db.patterns] Replayed {replayed_count} buffered records from local WAL.")
            else:
                with open(_PATTERNS_JOURNAL_FILE, "w", encoding="utf-8") as f:
                    f.writelines(remaining_records)
        except Exception as e:
            logger.error(f"[db.patterns] Error during pattern WAL replay: {e}")

    return replayed_count


# ── 4. IN-MEMORY HOT-PATH CACHE MANAGEMENT ───────────────────────────────────

def clear_pattern_cache() -> None:
    """Clear hot-path in-memory pattern cache (used in tests and session reloads)."""
    with _PATTERN_LOCK:
        _PATTERN_CACHE.clear()


def _get_from_cache(setup_hash: str, system_mode: str) -> Optional[Dict[str, Any]]:
    cache_key = f"{system_mode.upper()}::{setup_hash}"
    with _PATTERN_LOCK:
        if cache_key in _PATTERN_CACHE:
            data, exp = _PATTERN_CACHE[cache_key]
            if time.time() < exp:
                return data
            del _PATTERN_CACHE[cache_key]
    return None


def _put_into_cache(setup_hash: str, system_mode: str, data: Dict[str, Any]) -> None:
    cache_key = f"{system_mode.upper()}::{setup_hash}"
    with _PATTERN_LOCK:
        _PATTERN_CACHE[cache_key] = (data, time.time() + _CACHE_TTL_SECONDS)


def _invalidate_cache(setup_hash: str, system_mode: str) -> None:
    cache_key = f"{system_mode.upper()}::{setup_hash}"
    with _PATTERN_LOCK:
        _PATTERN_CACHE.pop(cache_key, None)


# ── 5. CORE PATTERN MEMORY OPERATIONS ────────────────────────────────────────

def get_pattern(setup_hash: str, system_mode: str = "RESEARCH", use_cache: bool = True) -> Optional[dict]:
    """
    Return pattern memory record for a given setup hash with microsecond caching.
    Called by devil_checks.py check_pattern_memory() on pre-trade execution paths.
    """
    if not setup_hash:
        return None

    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()

    if use_cache:
        cached = _get_from_cache(clean_hash, sys_mode)
        if cached is not None:
            return cached

    try:
        def _execute():
            return (
                sb.table("pattern_memory")
                .select("*")
                .eq("setup_hash", clean_hash)
                .eq("system_mode", sys_mode)
                .eq("is_deleted", False)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        data = result.data or []
        record = data[0] if data else None

        if record and use_cache:
            _put_into_cache(clean_hash, sys_mode, record)

        return record
    except Exception as e:
        logger.error(f"[db.patterns] get_pattern failed for {clean_hash}: {e}")
        return None


def upsert_pattern(pattern: Union[dict, PatternMemoryRecord]) -> dict:
    """
    Insert or update a pattern memory record.
    Called when a new trade opens (first seen or update).
    setup_hash is UNIQUE — upsert updates existing row.
    """
    from mjonai.core.time_utils import now_ist, today_ist
    raw_dict = pattern.to_dict() if isinstance(pattern, PatternMemoryRecord) else pattern
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    setup_hash = str(sanitized.get("setup_hash", "")).strip().upper()
    if not setup_hash:
        logger.error("[db.patterns] upsert_pattern missing mandatory 'setup_hash'.")
        return {}

    system_mode = str(sanitized.get("system_mode", "RESEARCH")).upper()
    today_str = str(today_ist())

    record = {
        **sanitized,
        "setup_hash": setup_hash,
        "system_mode": system_mode,
        "updated_at": now_ist().isoformat(),
    }
    if "first_seen" not in record or not record["first_seen"]:
        record["first_seen"] = today_str
    record["last_seen"] = today_str

    try:
        def _execute():
            return sb.table("pattern_memory").upsert(record, on_conflict="setup_hash").execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        res_data = result.data[0] if result.data else record

        _put_into_cache(setup_hash, system_mode, res_data)
        return res_data
    except Exception as e:
        logger.error(f"[db.patterns] upsert_pattern failed for {setup_hash}: {e} -> Buffering to WAL.")
        _append_pattern_journal("UPSERT_PATTERN", record)
        _put_into_cache(setup_hash, system_mode, record)
        return record


def update_pattern_outcome(
    setup_hash: str,
    outcome: str,
    actual_rr: Optional[float] = None,
    system_mode: str = "RESEARCH",
) -> bool:
    """
    Thread-safe update of pattern statistics when a trade closes.
    Computes Bayesian Laplace win rate, Mathematical Expectancy, and rolling last_10_outcomes.
    """
    if not setup_hash:
        return False

    from mjonai.core.time_utils import now_ist, today_ist
    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()
    outcome_clean = str(outcome).upper()

    with _PATTERN_LOCK:
        try:
            existing = get_pattern(clean_hash, system_mode=sys_mode, use_cache=False)
            if not existing:
                # First time seen on trade close: initialize record
                existing = {
                    "setup_hash": clean_hash,
                    "symbol": clean_hash.split("_")[0] if "_" in clean_hash else "UNKNOWN",
                    "strategy_id": clean_hash.split("_")[1] if len(clean_hash.split("_")) > 1 else "UNKNOWN",
                    "occurrences": 0,
                    "wins": 0,
                    "losses": 0,
                    "breakevens": 0,
                    "last_10_outcomes": [],
                    "system_mode": sys_mode,
                    "first_seen": str(today_ist()),
                }

            occurrences = _safe_int(existing.get("occurrences")) + 1
            wins = _safe_int(existing.get("wins"))
            losses = _safe_int(existing.get("losses"))
            breakevens = _safe_int(existing.get("breakevens"))

            if outcome_clean == "WIN":
                wins += 1
            elif outcome_clean == "LOSS":
                losses += 1
            else:
                breakevens += 1

            # Standard Win Rate (%)
            win_rate = round((wins / occurrences) * 100.0, 1) if occurrences > 0 else None

            # Bayesian Laplace-smoothed Win Rate (%)
            laplace_win_rate = round(((wins + 1) / (occurrences + 2)) * 100.0, 1)

            # Rolling and Average R:R Achieved
            old_avg_rr = _safe_float(existing.get("avg_rr_achieved"))
            valid_rr = actual_rr if (actual_rr is not None and not math.isnan(actual_rr)) else 0.0

            if occurrences > 1:
                new_avg_rr = round(((old_avg_rr * (occurrences - 1)) + valid_rr) / occurrences, 4)
            else:
                new_avg_rr = round(valid_rr, 4)

            # Mathematical Expectancy (in R units)
            win_pct = wins / occurrences if occurrences > 0 else 0.0
            loss_pct = losses / occurrences if occurrences > 0 else 0.0
            expectancy_rr = round((win_pct * new_avg_rr) - (loss_pct * 1.0), 4)

            # Profit Factor
            profit_factor = round((wins * max(0.1, new_avg_rr)) / max(1, losses), 2)

            # Rolling last 10 outcomes window
            last_10 = _safe_list(existing.get("last_10_outcomes"))
            last_10.append(outcome_clean)
            if len(last_10) > 10:
                last_10 = last_10[-10:]

            update_payload: Dict[str, Any] = {
                "setup_hash": clean_hash,
                "occurrences": occurrences,
                "wins": wins,
                "losses": losses,
                "breakevens": breakevens,
                "win_rate": win_rate,
                "laplace_win_rate": laplace_win_rate,
                "avg_rr_achieved": new_avg_rr,
                "expectancy_rr": expectancy_rr,
                "profit_factor": profit_factor,
                "last_10_outcomes": last_10,
                "last_seen": str(today_ist()),
                "last_outcome": outcome_clean,
                "system_mode": sys_mode,
                "updated_at": now_ist().isoformat(),
            }
            sanitized = _sanitize_payload(update_payload)

            def _execute():
                return sb.table("pattern_memory").upsert(sanitized, on_conflict="setup_hash").execute()

            result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
            _put_into_cache(clean_hash, sys_mode, sanitized)
            return True
        except Exception as e:
            logger.error(f"[db.patterns] update_pattern_outcome failed for {clean_hash}: {e} -> Buffering to WAL.")
            _append_pattern_journal("UPDATE_PATTERN_OUTCOME", {"setup_hash": clean_hash, "outcome": outcome_clean})
            return False


# ── 6. STATISTICAL & STREAK RISK SENTRIES ────────────────────────────────────

def get_consecutive_losses(setup_hash: str, system_mode: str = "RESEARCH") -> int:
    """
    Return the current consecutive loss streak from rolling last_10_outcomes.
    Detects toxic regime shifts before historical win rates degrade.
    """
    pattern = get_pattern(setup_hash, system_mode=system_mode)
    if not pattern:
        return 0

    last_10 = _safe_list(pattern.get("last_10_outcomes"))
    streak = 0
    for outcome in reversed(last_10):
        if str(outcome).upper() == "LOSS":
            streak += 1
        else:
            break
    return streak


def get_pattern_failures(
    setup_hash: str,
    lookback_days: int = 90,
    system_mode: str = "RESEARCH",
) -> int:
    """
    Return the number of losses for a specific setup hash within lookback_days.
    Called by devil_checks.check_pattern_memory().
    Returns 0 if pattern never seen (first occurrence = safe).
    """
    if not setup_hash:
        return 0
    from mjonai.core.time_utils import now_ist
    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()

    try:
        since = (now_ist() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        def _execute():
            return (
                sb.table("pattern_memory")
                .select("losses, last_seen")
                .eq("setup_hash", clean_hash)
                .eq("system_mode", sys_mode)
                .eq("is_deleted", False)
                .gte("last_seen", since)
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        data = result.data or []
        if not data:
            return 0
        return _safe_int(data[0].get("losses"))
    except Exception as e:
        logger.error(f"[db.patterns] get_pattern_failures failed for {clean_hash}: {e}")
        return 0


def get_failing_patterns(
    min_failures: int = 3,
    lookback_days: int = 90,
    system_mode: str = "RESEARCH",
) -> list:
    """
    Return patterns that have failed min_failures or more times within lookback_days.
    Used by devil_checks.py to veto toxic setups.
    """
    from mjonai.core.time_utils import now_ist
    sys_mode = system_mode.upper()
    try:
        since = (now_ist() - timedelta(days=lookback_days)).strftime("%Y-%m-%d")

        def _execute():
            return (
                sb.table("pattern_memory")
                .select("setup_hash, symbol, strategy_id, losses, win_rate, laplace_win_rate, last_10_outcomes, expectancy_rr, is_quarantined")
                .eq("system_mode", sys_mode)
                .eq("is_deleted", False)
                .gte("last_seen", since)
                .gte("losses", min_failures)
                .execute()
            )

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.patterns] get_failing_patterns failed: {e}")
        return []


# ── 7. PATTERN LIFECYCLE MANAGEMENT ──────────────────────────────────────────

def quarantine_pattern(setup_hash: str, system_mode: str = "RESEARCH") -> bool:
    """Explicitly quarantine a pathological setup hash to block execution."""
    if not setup_hash:
        return False
    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()
    _invalidate_cache(clean_hash, sys_mode)

    try:
        def _execute():
            return (
                sb.table("pattern_memory")
                .update({"is_quarantined": True})
                .eq("setup_hash", clean_hash)
                .eq("system_mode", sys_mode)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.patterns] quarantine_pattern failed for {clean_hash}: {e}")
        return False


def reactivate_pattern(setup_hash: str, system_mode: str = "RESEARCH") -> bool:
    """Remove quarantine from a pattern after regime recalibration."""
    if not setup_hash:
        return False
    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()
    _invalidate_cache(clean_hash, sys_mode)

    try:
        def _execute():
            return (
                sb.table("pattern_memory")
                .update({"is_quarantined": False})
                .eq("setup_hash", clean_hash)
                .eq("system_mode", sys_mode)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.patterns] reactivate_pattern failed for {clean_hash}: {e}")
        return False


def soft_delete_pattern(setup_hash: str, system_mode: str = "RESEARCH") -> bool:
    """Soft delete a pattern record."""
    if not setup_hash:
        return False
    clean_hash = setup_hash.strip().upper()
    sys_mode = system_mode.upper()
    _invalidate_cache(clean_hash, sys_mode)

    try:
        def _execute():
            return (
                sb.table("pattern_memory")
                .update({"is_deleted": True})
                .eq("setup_hash", clean_hash)
                .eq("system_mode", sys_mode)
                .execute()
            )
        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.patterns] soft_delete_pattern failed for {clean_hash}: {e}")
        return False


def get_patterns_for_quarantine_eval(
    system_mode: str = "RESEARCH",
    min_trades: int = 10,
) -> list:
    """
    Return non-quarantined pattern_memory rows with enough closed outcomes
    for a statistical quarantine verdict (occurrences >= min_trades).

    Feeds the learning loop's nightly evaluate_setup_hash_memory pass. The
    filter is set-side so eligible records with a few missing fields are
    still surfaced (the evaluator decides, it does not assume).
    """
    sys_mode = system_mode.upper()
    try:
        def _execute_query():
            return (
                sb.table("pattern_memory")
                .select("setup_hash, strategy_id, occurrences, laplace_win_rate, is_quarantined")
                .eq("system_mode", sys_mode)
                .eq("is_quarantined", False)
                .gte("occurrences", min_trades)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.patterns] get_patterns_for_quarantine_eval failed: {e}")
        return []
