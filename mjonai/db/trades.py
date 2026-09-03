"""
Module: db/trades.py

Purpose: Institutional Execution Management System (EMS) & Order Ledger,
         3-Tranche Partial Scaling, Stop-Loss Ratcheting, Implementation Shortfall (Slippage),
         3-Way Excursion Analytics (MAE/MFE/Giveback %), and Offline WAL Journal Replay.

Architectural Principles:
  1. Complete Multi-Asset Order Lifecycle (Equities, Options, Futures, Commodities).
  2. Implementation Shortfall & Slippage Attribution in Basis Points (bps).
  3. Atomic 3-Tranche Parent-Child Scaling State Machine (Target 1, Target 2, Runners).
  4. Dynamic Stop-Loss Ratcheting (INITIAL -> BREAKEVEN -> 1R_LOCKED -> TRAILING).
  5. 3-Way Excursion Analytics (MAE = Max Pain, MFE = Peak Profit, Giveback % at Exit).
  6. Complete Regulatory Fee & Tax Persistence (STT, GST, Turnover, Brokerage).
  7. Strict Environment Isolation (LIVE vs PAPER vs RESEARCH).
  8. Resilient Database Persistence with Exponential Backoff Retries (_execute_with_retry).
  9. Offline Durable WAL Journaling & Automated Replay (replay_trade_journal).
 10. Type-Safe Immutable Data Contracts (TradeRecord, TrancheRecord) & Float Sanitization.
 11. 100% Backwards-Compatible Public API for all callers.
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
_TRADES_JOURNAL_FILE = _STORAGE_DIR / "trades_journal.jsonl"


# ── 1. TYPE-SAFE IMMUTABLE DATA CONTRACTS ────────────────────────────────────

@dataclass(frozen=True)
class TradeRecord:
    """Immutable representation of a parent order/trade lifecycle."""
    symbol: str
    direction: str                     # "BUY" | "SELL"
    entry_price: float
    initial_sl: float
    current_sl: float
    target_price: float
    quantity: int
    strategy_id: str
    signal_id: Optional[str] = None
    asset_class: str = "EQUITY"        # "EQUITY" | "OPTIONS" | "FUTURES" | "COMMODITY"
    decision_price: Optional[float] = None
    slippage_bps: Optional[float] = None
    trailing_sl: Optional[float] = None
    sl_stage: str = "INITIAL"          # "INITIAL" | "BREAKEVEN" | "1R_LOCKED" | "TRAILING"
    quantity_remaining: Optional[int] = None
    uses_partial_exit: bool = True
    status: str = "OPEN"               # "OPEN" | "CLOSED" | "CANCELLED"
    system_mode: str = "RESEARCH"      # "RESEARCH" | "PAPER" | "LIVE"
    # Exit & P&L Attribution
    exit_price: Optional[float] = None
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    stt_tax: Optional[float] = None
    exchange_turnover_fee: Optional[float] = None
    brokerage: Optional[float] = None
    exit_reason: Optional[str] = None  # "TARGET" | "SL" | "TIME_BARRIER" | "KILL_LINE" | "MANUAL"
    actual_rr: Optional[float] = None
    # Excursion Analytics
    price_low_since_entry: Optional[float] = None
    price_high_since_entry: Optional[float] = None
    mae_pct: Optional[float] = None
    mfe_pct: Optional[float] = None
    giveback_pct: Optional[float] = None
    # Timestamps
    entry_time: Optional[str] = None
    exit_time: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    research_valid: bool = True
    is_deleted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        """Convert dataclass to clean dictionary omitting None fields."""
        d = asdict(self)
        return {k: v for k, v in d.items() if v is not None}


@dataclass(frozen=True)
class TrancheRecord:
    """Immutable representation of a child tranche partial execution."""
    trade_id: str
    tranche_number: int                # 1, 2, 3
    quantity: int
    target_price: Optional[float] = None
    target_rr: Optional[float] = None
    status: str = "OPEN"               # "OPEN" | "CLOSED" | "CANCELLED"
    exit_price: Optional[float] = None
    gross_pnl: Optional[float] = None
    net_pnl: Optional[float] = None
    exit_time: Optional[str] = None
    updated_at: Optional[str] = None
    is_deleted: bool = False

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

def _append_trade_journal(event_type: str, payload: Dict[str, Any]) -> None:
    """Durable local WAL journal for trade events during network disconnects."""
    try:
        _STORAGE_DIR.mkdir(parents=True, exist_ok=True)
        record = {
            "event_type": event_type,
            "payload": payload,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }
        with open(_TRADES_JOURNAL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")
    except Exception as e:
        logger.error(f"[db.trades] Failed to write local trade journal: {e}")


def replay_trade_journal() -> int:
    """
    Automated WAL Journal Replay Protocol for Trades.
    Flushes buffered offline records to Supabase.
    """
    if not _TRADES_JOURNAL_FILE.exists() or not is_db_connected():
        return 0

    replayed_count = 0
    remaining_records = []

    try:
        with open(_TRADES_JOURNAL_FILE, "r", encoding="utf-8") as f:
            lines = f.readlines()

        for line in lines:
            line_str = line.strip()
            if not line_str:
                continue
            try:
                entry = json.loads(line_str)
                event_type = entry.get("event_type")
                payload = entry.get("payload", {})

                if event_type == "INSERT_TRADE":
                    sb.table("trades").insert(payload).execute()
                    replayed_count += 1
                elif event_type == "UPDATE_TRADE":
                    trade_id = payload.get("id")
                    if trade_id:
                        up_payload = {k: v for k, v in payload.items() if k != "id"}
                        if "stt_tax" in up_payload:
                            if "stt" not in up_payload:
                                up_payload["stt"] = up_payload.pop("stt_tax")
                            else:
                                del up_payload["stt_tax"]
                        sb.table("trades").update(up_payload).eq("id", trade_id).execute()
                        replayed_count += 1
                elif event_type == "INSERT_TRANCHES":
                    tranches_data = payload.get("tranches", [])
                    if tranches_data:
                        sb.table("trade_tranches").insert(tranches_data).execute()
                        replayed_count += 1
                elif event_type == "CLOSE_TRANCHE":
                    tranche_id = payload.get("tranche_id")
                    if tranche_id:
                        up_payload = {k: v for k, v in payload.items() if k != "tranche_id"}
                        sb.table("trade_tranches").update(up_payload).eq("id", tranche_id).execute()
                        replayed_count += 1
                else:
                    remaining_records.append(line)
            except Exception as e:
                logger.warning(f"[db.trades] Replay item failed, keeping in WAL: {e}")
                remaining_records.append(line)

        if not remaining_records:
            _TRADES_JOURNAL_FILE.unlink(missing_ok=True)
            logger.info(f"[db.trades] Replayed {replayed_count} buffered records from local WAL.")
        else:
            with open(_TRADES_JOURNAL_FILE, "w", encoding="utf-8") as f:
                f.writelines(remaining_records)
    except Exception as e:
        logger.error(f"[db.trades] Error during trade WAL replay: {e}")

    return replayed_count


# ── 4. PRIMARY TRADE LIFECYCLE OPERATIONS ────────────────────────────────────

def insert_trade(trade: Union[dict, TradeRecord]) -> dict:
    """
    Insert a newly executed parent trade with implementation shortfall (slippage) tracking.
    """
    from mjonai.core.time_utils import now_ist
    raw_dict = trade.to_dict() if isinstance(trade, TradeRecord) else trade
    if not isinstance(raw_dict, dict) or not raw_dict:
        return {}

    sanitized = _sanitize_payload(raw_dict)
    now_str = now_ist().isoformat()
    entry_p = _safe_float(sanitized.get("entry_price"))

    # Calculate implementation shortfall / slippage in Basis Points (bps)
    decision_p = _safe_float(sanitized.get("decision_price"), default=entry_p)
    if decision_p > 0 and entry_p > 0 and "slippage_bps" not in sanitized:
        direction = str(sanitized.get("direction", "BUY")).upper()
        if direction == "BUY":
            slippage_bps = round(((entry_p - decision_p) / decision_p) * 10_000, 2)
        else:
            slippage_bps = round(((decision_p - entry_p) / decision_p) * 10_000, 2)
        sanitized["slippage_bps"] = slippage_bps

    import uuid
    record = {
        **sanitized,
        "id": sanitized.get("id") or str(uuid.uuid4()),
        "entry_time": sanitized.get("entry_time", now_str),
        "created_at": sanitized.get("created_at", now_str),
        "updated_at": now_str,
        "quantity_remaining": sanitized.get("quantity_remaining", sanitized.get("quantity")),
        "price_low_since_entry": sanitized.get("price_low_since_entry", entry_p),
        "price_high_since_entry": sanitized.get("price_high_since_entry", entry_p),
    }

    try:
        def _execute():
            return sb.table("trades").insert(record).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data[0] if result.data else record
    except Exception as e:
        if "asset_class" in record and "asset_class" in str(e):
            try:
                rec_fallback = {k: v for k, v in record.items() if k != "asset_class"}
                res = sb.table("trades").insert(rec_fallback).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
        logger.error(f"[db.trades] insert_trade failed: {e} -> Buffering to WAL.")
        _append_trade_journal("INSERT_TRADE", record)
        return record


def get_open_trades(system_mode: Optional[str] = None) -> list:
    """
    Return all trades with status OPEN.
    Called every minute by background monitor_trades().
    Never crashes — returns [] on network error to protect caller loop.
    """
    try:
        def _execute_query():
            query = (
                sb.table("trades")
                .select("*")
                .eq("status", "OPEN")
                .eq("is_deleted", False)
                .order("created_at", desc=True)
                .limit(100)
            )
            if system_mode:
                query = query.eq("system_mode", system_mode.upper())
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_open_trades failed: {e} — returning []")
        return []


def get_open_trade_by_symbol(symbol: str, system_mode: str = "RESEARCH") -> Optional[dict]:
    """
    Return first open trade for a given symbol, or None.
    Prevents duplicate position entries.
    """
    if not symbol:
        return None
    clean_sym = symbol.strip().upper()
    sys_mode = system_mode.upper()

    try:
        def _execute_query():
            return (
                sb.table("trades")
                .select("*")
                .eq("symbol", clean_sym)
                .eq("status", "OPEN")
                .eq("system_mode", sys_mode)
                .is_("exit_price", "null")
                .limit(1)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.trades] get_open_trade_by_symbol failed for {clean_sym}: {e}")
        return None


def get_open_trade_by_symbol_strict(symbol: str, system_mode: str = "RESEARCH") -> Optional[dict]:
    """
    Duplicate-position check for the ORDER PLACEMENT path.

    Unlike get_open_trade_by_symbol (which swallows errors and returns
    None), this RAISES on query failure. Callers must treat an exception
    as 'dedup unavailable' and refuse to open new positions — treating
    unknown as 'no duplicate' silently disables the duplicate sentry
    during database outages.
    """
    if not symbol:
        return None

    clean_sym = symbol.strip().upper()
    sys_mode = system_mode.upper()

    def _execute_query():
        return (
            sb.table("trades")
            .select("*")
            .eq("symbol", clean_sym)
            .eq("status", "OPEN")
            .eq("system_mode", sys_mode)
            .is_("exit_price", "null")
            .limit(1)
            .execute()
        )

    result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
    data = result.data or []
    return data[0] if data else None


def get_trade_by_id(trade_id: str) -> Optional[dict]:
    """Fetch a single trade record by UUID primary key."""
    if not trade_id:
        return None
    try:
        def _execute_query():
            return sb.table("trades").select("*").eq("id", trade_id).limit(1).execute()
        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        data = result.data or []
        return data[0] if data else None
    except Exception as e:
        logger.error(f"[db.trades] get_trade_by_id failed for {trade_id}: {e}")
        return None


def cancel_trade(trade_id: str, reason: str = "BROKER_REJECTED") -> bool:
    """
    Mark a reserved-but-never-executed trade as CANCELLED.

    Used by the ledger-first live dispatch path: when the broker rejects
    or errors after the ledger row was reserved, the row must not linger
    as OPEN (it would block future signals) nor count as a closed P&L.
    exit_price stays NULL so 'open position' style filters ignore it.
    """
    if not trade_id:
        return False
    from mjonai.core.time_utils import now_ist

    payload = {
        "id": trade_id,
        "status": "CANCELLED",
        "exit_reason": str(reason).upper(),
        "exit_time": now_ist().isoformat(),
        "updated_at": now_ist().isoformat(),
        "gross_pnl": 0.0,
        "net_pnl": 0.0,
    }

    sanitized = _sanitize_payload(payload)

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "id"}
            return sb.table("trades").update(up_dict).eq("id", trade_id).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] cancel_trade failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("UPDATE_TRADE", sanitized)
        return False


def get_trades_closed_today(system_mode: Optional[str] = None) -> list:
    """
    Return all trades CLOSED today filtered by exit_time (IST).
    Used by check_daily_loss() for Risk Kill Line enforcement.
    """
    from mjonai.core.time_utils import today_ist
    today = str(today_ist())

    try:
        def _execute_query():
            query = (
                sb.table("trades")
                .select("*")
                .eq("status", "CLOSED")
                .order("exit_time", desc=False)
                .gte("exit_time", f"{today}T00:00:00+05:30")
                .lte("exit_time", f"{today}T23:59:59+05:30")
            )
            if system_mode:
                query = query.eq("system_mode", system_mode.upper())
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_trades_closed_today failed: {e}")
        return []


def get_all_trades_today(system_mode: Optional[str] = None) -> list:
    """
    Return all trades (open + closed) created today (IST date) with server-side indexing.
    Eliminates legacy full-table scan.
    """
    from mjonai.core.time_utils import today_ist
    today = str(today_ist())

    try:
        def _execute_query():
            query = (
                sb.table("trades")
                .select("*")
                .gte("created_at", f"{today}T00:00:00+05:30")
                .lte("created_at", f"{today}T23:59:59+05:30")
            )
            if system_mode:
                query = query.eq("system_mode", system_mode.upper())
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_all_trades_today failed: {e}")
        return []


def close_trade(
    trade_id: str,
    exit_price: float,
    gross_pnl: float,
    net_pnl: float,
    exit_reason: str = "TARGET",
    taxes_charges: Optional[float] = None,
) -> bool:
    """
    Final settlement on trade close.
    Writes exit_time, exit_price, net P&L, and status=CLOSED.
    """
    if not trade_id:
        return False
    from mjonai.core.time_utils import now_ist

    update_payload = {
        "id": trade_id,
        "status": "CLOSED",
        "exit_price": round(exit_price, 2),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "exit_reason": str(exit_reason).upper(),
        "exit_time": now_ist().isoformat(),
        "updated_at": now_ist().isoformat(),
    }
    if taxes_charges is not None:
        update_payload["stt"] = round(taxes_charges, 2)

    sanitized = _sanitize_payload(update_payload)

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "id"}
            # Compare-and-swap guard: only an OPEN trade may transition
            # to CLOSED. Prevents duplicate closes from overwriting
            # settled P&L (tracker / dashboard / emergency close racing).
            return (
                sb.table("trades")
                .update(up_dict)
                .eq("id", trade_id)
                .eq("status", "OPEN")
                .execute()
            )

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] close_trade failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("UPDATE_TRADE", sanitized)
        return False


def update_trade_exit_fields(trade_id: str, fields: dict) -> bool:
    """
    Update exit-related fields for a trade on close.
    Single point of truth for all trade exit updates.
    """
    if not trade_id or not isinstance(fields, dict):
        return False
    from mjonai.core.time_utils import now_ist

    sanitized = _sanitize_payload(fields)
    sanitized["id"] = trade_id
    sanitized["updated_at"] = now_ist().isoformat()
    if "exit_time" not in sanitized:
        sanitized["exit_time"] = now_ist().isoformat()

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "id"}
            return sb.table("trades").update(up_dict).eq("id", trade_id).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] update_trade_exit_fields failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("UPDATE_TRADE", sanitized)
        return False


# ── 5. ATOMIC 3-TRANCHE SCALING & STOP LOSS RATCHET ──────────────────────────

def insert_trade_tranches(trade_id: str, tranches: Sequence[Union[dict, TrancheRecord]]) -> list:
    """
    Insert child tranches for a new trade (Tranche 1 50%, Tranche 2 30%, Runners 20%).
    """
    if not trade_id or not tranches:
        return []

    records = []
    for t in tranches:
        raw_dict = t.to_dict() if isinstance(t, TrancheRecord) else t
        if isinstance(raw_dict, dict) and raw_dict:
            clean = _sanitize_payload(raw_dict)
            records.append({
                "trade_id": trade_id,
                "tranche_number": _safe_int(clean.get("tranche_number"), default=1),
                "quantity": _safe_int(clean.get("quantity")),
                "target_price": clean.get("target_price"),
                "status": "OPEN",
            })

    if not records:
        return []

    try:
        def _execute():
            return sb.table("trade_tranches").insert(records).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return result.data or records
    except Exception as e:
        logger.error(f"[db.trades] insert_trade_tranches failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("INSERT_TRANCHES", {"trade_id": trade_id, "tranches": records})
        return records


def get_open_tranches(system_mode: Optional[str] = None) -> list:
    """Return all open tranches across all trades."""
    try:
        def _execute_query():
            return (
                sb.table("trade_tranches")
                .select("*")
                .eq("status", "OPEN")
                .eq("is_deleted", False)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_open_tranches failed: {e}")
        return []


def get_open_tranches_by_trade(trade_id: str) -> list:
    """Return all open tranches for a specific trade."""
    if not trade_id:
        return []
    try:
        def _execute_query():
            return (
                sb.table("trade_tranches")
                .select("*")
                .eq("trade_id", trade_id)
                .eq("status", "OPEN")
                .eq("is_deleted", False)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_open_tranches_by_trade failed for {trade_id}: {e}")
        return []


def get_closed_tranche_pnl(trade_id: str) -> dict:
    """
    Sum realized P&L across CLOSED tranches of a trade.

    Used by close_paper_trade to roll tranche economics into the parent
    settlement: the trades row is the single source of truth for realized
    whole-position P&L; trade_tranches rows remain execution detail.

    Returns {"gross_pnl": float, "net_pnl": float} — empty dict on failure so
    callers degrade to residual-only settlement instead of erroring mid-close.
    """
    if not trade_id:
        return {}
    try:
        def _execute_query():
            return (
                sb.table("trade_tranches")
                .select("gross_pnl,net_pnl")
                .eq("trade_id", str(trade_id))
                .eq("status", "CLOSED")
                .eq("is_deleted", False)
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        rows = result.data or []
        gross = round(sum(_safe_float(r.get("gross_pnl")) for r in rows), 2)
        net = round(sum(_safe_float(r.get("net_pnl")) for r in rows), 2)
        return {"gross_pnl": gross, "net_pnl": net}
    except Exception as e:
        logger.error(f"[db.trades] get_closed_tranche_pnl failed for {trade_id}: {e}")
        return {}


def close_tranche(
    tranche_id: str,
    exit_price: float,
    gross_pnl: float,
    net_pnl: float,
    update_parent_trade: bool = True,
) -> bool:
    """
    Mark a single tranche as closed and record realized P&L.
    """
    if not tranche_id:
        return False
    from mjonai.core.time_utils import now_ist

    now_str = now_ist().isoformat()
    update_payload = {
        "tranche_id": tranche_id,
        "exit_price": round(exit_price, 2),
        "gross_pnl": round(gross_pnl, 2),
        "net_pnl": round(net_pnl, 2),
        "exit_time": now_str,
        "status": "CLOSED",
        "updated_at": now_str,
    }
    sanitized = _sanitize_payload(update_payload)

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "tranche_id"}
            return sb.table("trade_tranches").update(up_dict).eq("id", tranche_id).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] close_tranche failed for {tranche_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("CLOSE_TRANCHE", sanitized)
        return False


def update_trade_sl(
    trade_id: str,
    sl_stage: str,
    current_sl: float,
    trailing_sl: Optional[float] = None,
    quantity_remaining: Optional[int] = None,
) -> bool:
    """
    Update Stop Loss stage and value for an active trade (INITIAL -> BREAKEVEN -> 1R_LOCKED -> TRAILING).
    """
    if not trade_id:
        return False
    from mjonai.core.time_utils import now_ist

    update_data: Dict[str, Any] = {
        "id": trade_id,
        "sl_stage": str(sl_stage).upper(),
        "current_sl": round(current_sl, 2),
        "updated_at": now_ist().isoformat(),
    }
    if trailing_sl is not None and not math.isnan(trailing_sl):
        update_data["trailing_sl"] = round(trailing_sl, 2)
    if quantity_remaining is not None:
        update_data["quantity_remaining"] = quantity_remaining

    sanitized = _sanitize_payload(update_data)

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "id"}
            return sb.table("trades").update(up_dict).eq("id", trade_id).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] update_trade_sl failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("UPDATE_TRADE", sanitized)
        return False


def get_trades_with_open_tranches() -> list:
    """
    Return all trades that use partial exit logic and still have open tranches.
    """
    try:
        def _execute_query():
            return (
                sb.table("trades")
                .select("*")
                .eq("uses_partial_exit", True)
                .eq("status", "OPEN")
                .is_("exit_price", "null")
                .execute()
            )

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_trades_with_open_tranches failed: {e}")
        return []


# ── 6. 3-WAY EXCURSION ANALYTICS (MAE, MFE & PROFIT GIVEBACK %) ──────────────

def update_trade_price_extremes(
    trade_id: str,
    current_price: float,
    entry_price: Optional[float] = None,
    direction: str = "BUY",
    price_low_since_entry: Optional[float] = None,
    price_high_since_entry: Optional[float] = None,
) -> Optional[dict]:
    """
    Update running price low (MAE) and price high (MFE) since entry.
    Minimizes DB writes by only updating when a new high/low extreme is discovered.
    """
    if not trade_id or current_price <= 0 or math.isnan(current_price):
        return None
    from mjonai.core.time_utils import now_ist

    try:
        if price_low_since_entry is not None and price_high_since_entry is not None and entry_price is not None:
            actual_entry = _safe_float(entry_price)
            trade_dir = str(direction or "BUY").upper()
            current_low = _safe_float(price_low_since_entry, default=current_price)
            current_high = _safe_float(price_high_since_entry, default=current_price)
        else:
            def _fetch_extremes():
                return (
                    sb.table("trades")
                    .select("entry_price, price_low_since_entry, price_high_since_entry, signal_direction")
                    .eq("id", trade_id)
                    .limit(1)
                    .execute()
                )

            fetch_res = _execute_with_retry(_fetch_extremes, max_retries=2, initial_delay=0.1)
            data = fetch_res.data or []
            if not data:
                return None

            row = data[0]
            actual_entry = _safe_float(entry_price or row.get("entry_price"))
            trade_dir = str(direction or row.get("signal_direction") or "BUY").upper()
            current_low = _safe_float(row.get("price_low_since_entry"), default=current_price)
            current_high = _safe_float(row.get("price_high_since_entry"), default=current_price)

        needs_update = False
        update_data: Dict[str, Any] = {"id": trade_id, "updated_at": now_ist().isoformat()}

        # New minimum found
        if current_price < current_low:
            current_low = round(current_price, 2)
            update_data["price_low_since_entry"] = current_low
            needs_update = True

        # New maximum found
        if current_price > current_high:
            current_high = round(current_price, 2)
            update_data["price_high_since_entry"] = current_high
            needs_update = True

        # Calculate MAE % (Max Pain) and MFE % (Peak Profit)
        if actual_entry > 0:
            if trade_dir == "BUY":
                mae_pct = round(((current_low - actual_entry) / actual_entry) * 100.0, 2)
                mfe_pct = round(((current_high - actual_entry) / actual_entry) * 100.0, 2)
            else:
                mae_pct = round(((actual_entry - current_high) / actual_entry) * 100.0, 2)
                mfe_pct = round(((actual_entry - current_low) / actual_entry) * 100.0, 2)

            update_data["mae_pct"] = min(0.0, mae_pct)
            update_data["mfe_pct"] = max(0.0, mfe_pct)

        if needs_update:
            sanitized = _sanitize_payload(update_data)

            def _execute_update():
                up_dict = {k: v for k, v in sanitized.items() if k != "id"}
                return sb.table("trades").update(up_dict).eq("id", trade_id).execute()

            _execute_with_retry(_execute_update, max_retries=2, initial_delay=0.1)
            return update_data

        return None
    except Exception as e:
        logger.error(f"[db.trades] update_trade_price_extremes failed for {trade_id}: {e}")
        return None


# ── 7. RESEARCH & AUDIT TELEMETRY ────────────────────────────────────────────

def update_trade_research_fields(trade_id: str, fields: dict) -> bool:
    """
    Update research context fields on a trade at open time.
    """
    if not trade_id or not isinstance(fields, dict):
        return False
    from mjonai.core.time_utils import now_ist

    sanitized = _sanitize_payload(fields)
    sanitized["id"] = trade_id
    sanitized["updated_at"] = now_ist().isoformat()

    try:
        def _execute():
            up_dict = {k: v for k, v in sanitized.items() if k != "id"}
            return sb.table("trades").update(up_dict).eq("id", trade_id).execute()

        result = _execute_with_retry(_execute, max_retries=2, initial_delay=0.1)
        return bool(result.data)
    except Exception as e:
        logger.error(f"[db.trades] update_trade_research_fields failed for {trade_id}: {e} -> Buffering to WAL.")
        _append_trade_journal("UPDATE_TRADE", sanitized)
        return False


def get_research_trades(
    system_mode: str = "RESEARCH",
    strategy_id: Optional[str] = None,
    limit: int = 500,
) -> list:
    """
    Return closed trades with research_valid = TRUE for Alphalens / QuantStats.
    Strictly isolated by system_mode.
    """
    sys_mode = system_mode.upper()
    try:
        def _execute_query():
            query = (
                sb.table("trades")
                .select("*")
                .eq("research_valid", True)
                .eq("system_mode", sys_mode)
                .not_.is_("exit_price", "null")
                .order("created_at", desc=False)
                .limit(limit)
            )
            if strategy_id:
                query = query.eq("strategy_id", strategy_id)
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_research_trades failed: {e}")
        return []


def get_all_closed_trades(limit: int = 1000, system_mode: Optional[str] = None) -> list:
    """
    Return all closed trades regardless of research_valid.
    Used by dashboard trade logs and performance summaries.
    """
    try:
        def _execute_query():
            query = (
                sb.table("trades")
                .select("*")
                .not_.is_("exit_price", "null")
                .order("created_at", desc=False)
                .limit(limit)
            )
            if system_mode:
                query = query.eq("system_mode", system_mode.upper())
            return query.execute()

        result = _execute_with_retry(_execute_query, max_retries=2, initial_delay=0.1)
        return result.data or []
    except Exception as e:
        logger.error(f"[db.trades] get_all_closed_trades failed: {e}")
        return []
