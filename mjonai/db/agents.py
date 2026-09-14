"""
Module: db/agents.py

Purpose: Multi-LLM AI Committee Telemetry, Call Logging, Bayesian Accuracy Tracking,
         Token Usage & Latency Profiling, and Offline WAL Journal Replay.

Architectural Principles:
  1. Complete Multi-Agent Lifecycle Logging (Bull, Bear, Devil, Economist, Supervisor).
  2. High-Throughput Vectorized Ingestion (insert_agent_logs_bulk for atomic debate batches).
  3. Bayesian Laplace-Smoothed Accuracy & Multi-Role Verdict Directional Intelligence.
  4. Token Consumption, API Latency & Cost Telemetry Aggregation.
  5. Single Aggregated Committee Scoreboard (get_all_agents_accuracy_summary).
  6. Resilient Database Persistence with Exponential Backoff Retries (_execute_with_retry).
  7. Offline Durable WAL Journaling & Automated Replay (replay_agent_journal).
  8. Type-Safe Immutable Data Contract (AgentLogRecord) with covariant parameters.
  9. 100% Backwards-Compatible Public API for all callers.
"""

from dataclasses import dataclass, field, asdict
from datetime import date, datetime, timedelta, timezone
import json
import logging
import math
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Union

from mjonai.db.client import sb, is_db_connected, execute_with_retry as _execute_with_retry

logger = logging.getLogger(__name__)

# Local durable journal directory
_STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"  # repo root (ADR-0008)
_AGENT_JOURNAL_FILE = _STORAGE_DIR / "agent_logs_journal.jsonl"


# ── 1. TYPE-SAFE IMMUTABLE AGENT LOG CONTRACT ────────────────────────────────

@dataclass(frozen=True)
class AgentLogRecord:
    """
    Immutable representation of an AI agent's analysis during a trade debate.
    Captures complete qualitative reasoning, confidence, and telemetry.
    """
    agent_name: str                    # "BULL" | "BEAR" | "SUPERVISOR"
    signal_id: str                     # UUID link to signal_intelligence_log
    raw_verdict: str                   # "BUY" | "STRONG_BUY" | "SELL" | "REJECT" | "APPROVE" | "NEUTRAL"
    confidence_given: float            # 0.0 to 1.0 confidence score
    key_reasons: List[str] = field(default_factory=list)
    concerns: List[str] = field(default_factory=list)
    full_response: Optional[str] = None
    latency_ms: Optional[float] = None
    prompt_tokens: Optional[int] = None
    completion_tokens: Optional[int] = None
    agent_model: str = "gpt-4o"
    fallback_used: bool = False
    system_mode: str = "RESEARCH"
    called_at: Optional[str] = None
    updated_at: Optional[str] = None
    # Outcome attribution fields
    actual_outcome: Optional[str] = None
    actual_rr: Optional[float] = None
    was_correct: Optional[bool] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to clean dictionary omitting None fields."""
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


def _safe_float(val: Any, default: float = 0.0) -> float:
    from mjonai.core.numeric import safe_float
    return safe_float(val, default)


def _safe_int(val: Any, default: int = 0) -> int:
    """Safely convert any JSON/database value to int."""
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


# ── 3. LOCAL DURABLE WAL JOURNAL ─────────────────────────────────────────────

def _append_agent_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """Durable local WAL journal for agent logs during network disconnects."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_AGENT_JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"[db.agents] Failed to write local journal: {e}")


def replay_agent_journal() -> int:
    """
    Automated WAL Journal Replay Protocol for Agent Logs.
    Flushes buffered offline records to Supabase.
    """
    if not _AGENT_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed_count = 0
    remaining_records = []

    try:
        with open(_AGENT_JOURNAL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
                event_type = entry.get("event_type")
                payload = entry.get("payload", {})

                if event_type == "INSERT_AGENT_LOG":
                    sb.table("agent_logs").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "UPDATE_AGENT_OUTCOME":
                    log_id = payload.get("id")
                    if log_id:
                        up_payload = {k: v for k, v in payload.items() if k != "id"}
                        sb.table("agent_logs").update(up_payload).eq("id", log_id).execute()
                        replayed_count += 1
                else:
                    remaining_records.append(line)
            except Exception as e:
                logger.warning(f"[db.agents] Replay item failed, keeping in WAL: {e}")
                remaining_records.append(line)

        if not remaining_records:
            _AGENT_JOURNAL_FILE.unlink(missing_ok=True)
            logger.info(f"[db.agents] Replayed {replayed_count} buffered records from local WAL.")
        else:
            with open(_AGENT_JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(remaining_records)
    except Exception as e:
        logger.error(f"[db.agents] Error during agent WAL replay: {e}")

    return replayed_count


# ── 4. CORE AGENT LOGGING OPERATIONS ─────────────────────────────────────────

def insert_agent_log(log: Union[dict, AgentLogRecord]) -> dict:
    """
    Insert a single agent call record into agent_logs.
    Called after every LLM evaluation.
    """
    from mjonai.core.time_utils import now_ist
    raw_dict = log.to_dict() if isinstance(log, AgentLogRecord) else log
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    # Ensure integer fields match Postgres integer column types
    if "latency_ms" in sanitized and sanitized["latency_ms"] is not None:
        sanitized["latency_ms"] = int(round(float(sanitized["latency_ms"])))
    if "prompt_tokens" in sanitized and sanitized["prompt_tokens"] is not None:
        sanitized["prompt_tokens"] = int(round(float(sanitized["prompt_tokens"])))
    if "completion_tokens" in sanitized and sanitized["completion_tokens"] is not None:
        sanitized["completion_tokens"] = int(round(float(sanitized["completion_tokens"])))

    now_str = now_ist().isoformat()
    record = {
        **sanitized,
        "called_at": sanitized.get("called_at", now_str),
        "updated_at": now_str,
    }

    try:
        def _execute():
            return sb.table("agent_logs").insert(record).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        logger.error(f"[db.agents] insert_agent_log failed: {e} -> Buffering to WAL.")
        _append_agent_journal("INSERT_AGENT_LOG", record)
        return record


def insert_agent_logs_bulk(logs: Sequence[Union[dict, AgentLogRecord]]) -> List[dict]:
    """
    High-throughput batch insertion for full AI committee debates.
    Reduces N sequential network roundtrips into a single vectorized query.
    """
    from mjonai.core.time_utils import now_ist
    if not logs:
        return []

    now_str = now_ist().isoformat()
    sanitized_records = []

    for l in logs:
        raw_dict = l.to_dict() if isinstance(l, AgentLogRecord) else l
        if isinstance(raw_dict, dict) and raw_dict:
            clean = _sanitize_payload(raw_dict)
            if "latency_ms" in clean and clean["latency_ms"] is not None:
                clean["latency_ms"] = int(round(float(clean["latency_ms"])))
            if "prompt_tokens" in clean and clean["prompt_tokens"] is not None:
                clean["prompt_tokens"] = int(round(float(clean["prompt_tokens"])))
            if "completion_tokens" in clean and clean["completion_tokens"] is not None:
                clean["completion_tokens"] = int(round(float(clean["completion_tokens"])))
            if "called_at" not in clean:
                clean["called_at"] = now_str
            clean["updated_at"] = now_str
            sanitized_records.append(clean)

    if not sanitized_records:
        return []

    try:
        def _execute():
            return sb.table("agent_logs").insert(sanitized_records).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or sanitized_records
    except Exception as e:
        logger.error(f"[db.agents] insert_agent_logs_bulk failed for {len(sanitized_records)} items: {e}")
        for rec in sanitized_records:
            _append_agent_journal("INSERT_AGENT_LOG", rec)
        return sanitized_records


# ── 5. OUTCOME ATTRIBUTION & MULTI-ROLE EVALUATION ───────────────────────────

def evaluate_verdict_accuracy(agent_name: str, verdict: str, outcome: str) -> Optional[bool]:
    """
    Directional accuracy evaluator accounting for specialized committee roles.
    BULL / SUPERVISOR: BUY/APPROVE + WIN = True, REJECT/SELL + LOSS = True
    BEAR / DEVIL:      WARN/REJECT/SELL + LOSS = True, BUY/APPROVE + WIN = True
    """
    v_clean = str(verdict).strip().upper()
    o_clean = str(outcome).strip().upper()
    a_clean = str(agent_name).strip().upper()

    if o_clean == "BREAKEVEN":
        return None

    is_bullish = v_clean in ("BUY", "STRONG_BUY", "APPROVE", "BULLISH")
    is_bearish = v_clean in ("SELL", "REJECT", "BEARISH", "HIGH_RISK", "VETO")

    if o_clean == "WIN":
        if is_bullish:
            return True
        elif is_bearish:
            return False
    elif o_clean == "LOSS":
        if is_bearish:
            return True
        elif is_bullish:
            return False

    return None


def update_agent_log_outcome(
    signal_id: str,
    actual_outcome: str,
    actual_rr: Optional[float] = None,
) -> bool:
    """
    Update all agent_log rows for a signal with trade outcome.
    Evaluates was_correct based on directional role intelligence.
    """
    if not signal_id:
        return False
    from mjonai.core.time_utils import now_ist

    try:
        def _fetch_rows():
            return (
                sb.table("agent_logs")
                .select("id, agent_name, raw_verdict")
                .eq("signal_id", signal_id)
                .execute()
            )

        fetch_res = _execute_with_retry(_fetch_rows, max_retries=2, initial_delay=0.1)
        rows = fetch_res.data or []
        if not rows:
            return False

        now_str = now_ist().isoformat()
        clean_rr = round(actual_rr, 4) if actual_rr is not None and not math.isnan(actual_rr) else None
        success = True

        for row in rows:
            agent_name = str(row.get("agent_name") or "")
            verdict = str(row.get("raw_verdict") or "")
            was_correct = evaluate_verdict_accuracy(agent_name, verdict, actual_outcome)

            update_payload = {
                "actual_outcome": str(actual_outcome).upper(),
                "actual_rr": clean_rr,
                "was_correct": was_correct,
                "updated_at": now_str,
            }
            sanitized = _sanitize_payload(update_payload)

            try:
                def _execute_update(log_id=row["id"], p=sanitized):
                    return sb.table("agent_logs").update(p).eq("id", log_id).execute()

                _execute_with_retry(_execute_update, max_retries=2, initial_delay=0.1)
            except Exception as e:
                logger.error(f"[db.agents] Failed updating agent row {row.get('id')}: {e}")
                _append_agent_journal("UPDATE_AGENT_OUTCOME", {"id": row.get("id"), **sanitized})
                success = False

        return success
    except Exception as e:
        logger.error(f"[db.agents] update_agent_log_outcome failed for signal {signal_id}: {e}")
        return False


# ── 6. STATISTICAL ACCURACY & TELEMETRY SCORING ──────────────────────────────

def get_agent_accuracy(
    agent_name: str,
    system_mode: str = "RESEARCH",
    lookback_days: int = 30,
) -> dict:
    """
    Return rolling accuracy statistics and Laplace-smoothed confidence for a given agent.
    """
    from mjonai.core.time_utils import now_ist
    clean_agent = agent_name.strip().upper()
    sys_mode = system_mode.upper()

    try:
        since = (now_ist() - timedelta(days=lookback_days)).isoformat()

        def _execute_query():
            return (
                sb.table("agent_logs")
                .select("was_correct, raw_verdict, actual_outcome")
                .eq("agent_name", clean_agent)
                .eq("system_mode", sys_mode)
                .gte("called_at", since)
                .not_.is_("was_correct", "null")
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []
        if not rows:
            return {
                "agent_name": clean_agent,
                "total_calls": 0,
                "correct_calls": 0,
                "accuracy_pct": None,
                "laplace_accuracy_pct": None,
                "lookback_days": lookback_days,
                "system_mode": sys_mode,
            }

        total = len(rows)
        correct = sum(1 for r in rows if r.get("was_correct") is True)
        accuracy_pct = round((correct / total) * 100.0, 1) if total > 0 else None
        laplace_accuracy_pct = round(((correct + 1) / (total + 2)) * 100.0, 1)

        return {
            "agent_name": clean_agent,
            "total_calls": total,
            "correct_calls": correct,
            "accuracy_pct": accuracy_pct,
            "laplace_accuracy_pct": laplace_accuracy_pct,
            "lookback_days": lookback_days,
            "system_mode": sys_mode,
        }
    except Exception as e:
        logger.error(f"[db.agents] get_agent_accuracy failed for {clean_agent}: {e}")
        return {
            "agent_name": clean_agent,
            "total_calls": 0,
            "correct_calls": 0,
            "accuracy_pct": None,
            "laplace_accuracy_pct": None,
            "lookback_days": lookback_days,
            "system_mode": sys_mode,
        }


def get_all_agents_accuracy_summary(
    system_mode: str = "RESEARCH",
    lookback_days: int = 30,
) -> List[dict]:
    """
    Return comprehensive committee scoreboard in a single aggregated query.
    Dynamically discovers all active agents (Bull, Bear, Supervisor, and any
    future advisors) to support open-ended multi-agent expansion.
    """
    from mjonai.core.time_utils import now_ist
    sys_mode = system_mode.upper()
    standard_agents = ["BULL", "BEAR", "SUPERVISOR"]

    try:
        since = (now_ist() - timedelta(days=lookback_days)).isoformat()

        def _execute_query():
            return (
                sb.table("agent_logs")
                .select("agent_name, was_correct")
                .eq("system_mode", sys_mode)
                .gte("called_at", since)
                .not_.is_("was_correct", "null")
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []

        # Group stats by agent dynamically
        agent_stats: Dict[str, Dict[str, int]] = {a: {"total": 0, "correct": 0} for a in standard_agents}
        for r in rows:
            name = str(r.get("agent_name") or "").strip().upper()
            if not name:
                continue
            if name not in agent_stats:
                agent_stats[name] = {"total": 0, "correct": 0}
            agent_stats[name]["total"] += 1
            if r.get("was_correct") is True:
                agent_stats[name]["correct"] += 1

        summary = []
        for name, stats in agent_stats.items():
            tot = stats["total"]
            cor = stats["correct"]
            summary.append({
                "agent_name": name,
                "total_calls": tot,
                "correct_calls": cor,
                "accuracy_pct": round((cor / tot) * 100.0, 1) if tot > 0 else None,
                "laplace_accuracy_pct": round(((cor + 1) / (tot + 2)) * 100.0, 1),
                "lookback_days": lookback_days,
                "system_mode": sys_mode,
            })
        return summary
    except Exception as e:
        logger.error(f"[db.agents] get_all_agents_accuracy_summary failed: {e}")
        return [
            {
                "agent_name": a,
                "total_calls": 0,
                "correct_calls": 0,
                "accuracy_pct": None,
                "laplace_accuracy_pct": None,
                "lookback_days": lookback_days,
                "system_mode": sys_mode,
            }
            for a in standard_agents
        ]


def get_agent_telemetry_summary(
    system_mode: str = "RESEARCH",
    lookback_days: int = 30,
) -> dict:
    """
    Aggregate token consumption, latency, and estimated cost across all LLMs.
    """
    from mjonai.core.time_utils import now_ist
    sys_mode = system_mode.upper()

    try:
        since = (now_ist() - timedelta(days=lookback_days)).isoformat()

        def _execute_query():
            return (
                sb.table("agent_logs")
                .select("agent_name, agent_model, latency_ms, prompt_tokens, completion_tokens")
                .eq("system_mode", sys_mode)
                .gte("called_at", since)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []
        if not rows:
            return {
                "total_calls": 0,
                "total_prompt_tokens": 0,
                "total_completion_tokens": 0,
                "avg_latency_ms": 0.0,
                "estimated_cost_usd": 0.0,
                "lookback_days": lookback_days,
                "system_mode": sys_mode,
            }

        total_calls = len(rows)
        total_p_tokens = sum(_safe_int(r.get("prompt_tokens")) for r in rows)
        total_c_tokens = sum(_safe_int(r.get("completion_tokens")) for r in rows)
        latencies = [_safe_float(r.get("latency_ms")) for r in rows if r.get("latency_ms") is not None]
        avg_latency = round(sum(latencies) / len(latencies), 1) if latencies else 0.0

        # Estimated cost model: ~$5 per 1M prompt tokens, ~$15 per 1M completion tokens
        est_cost = round(((total_p_tokens / 1_000_000) * 5.0) + ((total_c_tokens / 1_000_000) * 15.0), 4)

        return {
            "total_calls": total_calls,
            "total_prompt_tokens": total_p_tokens,
            "total_completion_tokens": total_c_tokens,
            "avg_latency_ms": avg_latency,
            "estimated_cost_usd": est_cost,
            "lookback_days": lookback_days,
            "system_mode": sys_mode,
        }
    except Exception as e:
        logger.error(f"[db.agents] get_agent_telemetry_summary failed: {e}")
        return {
            "total_calls": 0,
            "total_prompt_tokens": 0,
            "total_completion_tokens": 0,
            "avg_latency_ms": 0.0,
            "estimated_cost_usd": 0.0,
            "lookback_days": lookback_days,
            "system_mode": sys_mode,
        }


# ── 7. CALIBRATION INPUT & CROSS-AGENT LEARNING LOOP ─────────────────────────

def get_agent_logs_for_calibration(
    lookback_days: int = 30,
) -> List[Dict[str, Any]]:
    """
    Pull the outcome-tagged agent rows the calibration loop consumes.

    Each affected row must carry confidence (the forecast) and a resolved
    win/loss (the realized outcome) so Brier skill and rank-IC can be
    computed. Rows without an attributed outcome are excluded — a trade that
    never closed must not water down calibration with a phantom sample.

    Returns raw rows: agent_name, confidence_given, actual_outcome, system_mode.
    """
    from mjonai.core.time_utils import now_ist
    try:
        since = (now_ist() - timedelta(days=lookback_days)).isoformat()

        def _execute_query():
            return (
                sb.table("agent_logs")
                .select("signal_id, agent_name, confidence_given, actual_outcome, system_mode, was_correct")
                .gte("called_at", since)
                .in_("actual_outcome", ["WIN", "LOSS"])
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.agents] get_agent_logs_for_calibration failed: {e}")
        return []
