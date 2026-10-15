"""
Module: risk/emergency_triggers.py
Purpose: SOTA Multi-Tier Emergency Circuit Breakers & Portfolio Risk Sentries.
         Monitors real-time portfolio Mark-to-Market (MTM) P&L every minute, enforces
         the 15% Lifetime Kill Line, 3% Daily Loss Stop, Soft Stop, Flash-Crash
         Drop Velocity Sentries, and Remote Telegram Manual Pauses.

The 5 Emergency Tiers:
  1. Soft Stop (3 consecutive losses -> SOFT_STOP_DURATION_MINUTES cooling-off
     pause; 120 minutes by default, configurable via core/runtime_config.py).
  2. Flash-Crash Velocity Sentry (rapid >1.5% equity drop in <5 mins -> 15-min pause).
  3. Daily Risk Stop (daily realized + unrealized loss >= 3.0% -> halts trading for today).
  4. The 15% Kill Line (session circuit vs. today's peak + lifetime ruin protection
     vs. the persisted lifetime peak watermark -> auto-liquidate & lock; arms
     in any non-RESEARCH mode, never in RESEARCH).
  5. Remote Telegram Manual Pause (/pause & /resume commands).
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
import threading
from typing import Tuple, Dict, Any, List, Optional, Sequence, Union

from mjonai.core.time_utils import now_ist, today_ist
from mjonai.core.runtime_config import SOFT_STOP_DURATION_MINUTES
from mjonai.core.constants import (
    TOTAL_CAPITAL,
    DAILY_LOSS_LIMIT_PCT,
    KILL_LINE_PCT,
    CONSECUTIVE_LOSS_LIMIT,
    SYSTEM_MODE,
)

logger = logging.getLogger(__name__)

# State lock
_RISK_LOCK = threading.RLock()

# Local rolling equity history for Flash-Crash Velocity detection (timestamp, equity)
_equity_history: List[Tuple[datetime, float]] = []

# State
_state: Dict[str, Any] = {
    "risk_stop_active": False,
    "soft_stop_active": False,
    "soft_stop_until": None,
    "flash_crash_pause_active": False,
    "flash_crash_until": None,
    "kill_line_active": False,
    "peak_equity": TOTAL_CAPITAL,
    "consecutive_losses": 0,
    "manual_pause_active": False,
    "manual_pause_reason": None,
}


# ── 1. TYPE-SAFE DATA CONTRACT ───────────────────────────────────────────────

@dataclass(frozen=True)
class EmergencyRiskStatus:
    """Immutable contract representing the complete real-time portfolio risk state."""
    trading_allowed: bool
    kill_line_active: bool
    risk_stop_active: bool
    soft_stop_active: bool
    manual_pause_active: bool
    flash_crash_pause_active: bool
    current_drawdown_pct: float
    daily_loss_pct: float
    peak_equity: float
    current_equity: float
    realized_pnl_today: float
    unrealized_pnl: float
    total_pnl_today: float
    reasons: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# ── 2. DEFENSIVE FLOAT CONVERTER & TELEGRAM SENTRY ───────────────────────────

from mjonai.core.numeric import safe_float as _safe_float


def _safe_send_telegram(msg: str) -> None:
    """Send Telegram message safely without crashing caller on network failures."""
    try:
        from mjonai.communication.telegram import send_message
        send_message(msg)
    except Exception as e:
        logger.warning(f"[EmergencyTriggers] Non-critical: Could not send Telegram alert: {e}")


def _log_risk_event(event_type: str, message: str, level: str = "WARNING", system_mode: str = "RESEARCH") -> None:
    """Log immutable risk event to Supabase via repository."""
    try:
        from mjonai.db.repository import insert_risk_event
        insert_risk_event(event_type=event_type, message=message, level=level, system_mode=system_mode)
    except Exception as e:
        logger.warning(f"[EmergencyTriggers] Failed to log risk event to DB: {e}")


# ── 3. STATE RESTORATION & DAILY RESET ───────────────────────────────────────

def get_state() -> dict:
    """Return thread-safe snapshot copy of current risk state."""
    with _RISK_LOCK:
        return _state.copy()


def restore_risk_state(system_mode: Optional[str] = None) -> dict:
    """
    Restore risk state from DB after server restart.
    Reconstructs peak equity, today's realized P&L, and active stops.
    """
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    restored = {}

    with _RISK_LOCK:
        try:
            from mjonai.db.repository import (
                get_trades_closed_today,
                load_peak_equity,
                get_current_drawdown_pct,
                insert_system_log,
            )

            # 1. Restore peak equity
            peak = load_peak_equity(default=TOTAL_CAPITAL)
            _state["peak_equity"] = peak
            restored["peak_equity"] = peak

            # 2. Calculate today's realized P&L
            closed_today = get_trades_closed_today(system_mode=sys_mode) or []
            realized_pnl = sum(_safe_float(t.get("net_pnl")) for t in closed_today)
            restored["realized_pnl_today"] = realized_pnl

            # 3. Restore Risk Stop if daily loss already breached
            if realized_pnl < 0:
                loss_pct = (abs(realized_pnl) / TOTAL_CAPITAL) * 100.0
                if loss_pct >= DAILY_LOSS_LIMIT_PCT:
                    _state["risk_stop_active"] = True
                    restored["risk_stop_restored"] = True
                    logger.warning(
                        f"[Restore] Risk Stop re-activated — today's loss {loss_pct:.1f}% >= {DAILY_LOSS_LIMIT_PCT}%"
                    )

            # 4. Restore Kill Line if drawdown >= 15% (P0.6 ruling 2026-09-20:
            # a) measured from today's session baseline + realized P&L against the
            #    persisted lifetime peak watermark — not a phantom TOTAL_CAPITAL base
            #    after profitable history; b) armed in any non-RESEARCH mode).
            current_equity = _session_baseline_equity(sys_mode) + realized_pnl
            drawdown_pct = get_current_drawdown_pct(current_equity, default_capital=TOTAL_CAPITAL)
            restored["current_drawdown_pct"] = drawdown_pct

            if sys_mode != "RESEARCH" and drawdown_pct >= KILL_LINE_PCT:
                _state["kill_line_active"] = True
                restored["kill_line_restored"] = True
                logger.critical(
                    f"[Restore] Kill Line re-activated — drawdown {drawdown_pct:.1f}% >= {KILL_LINE_PCT}%"
                )

            # 5. Restore consecutive losses
            consecutive = 0
            for trade in reversed(closed_today):
                net_pnl = _safe_float(trade.get("net_pnl"))
                if net_pnl < 0:
                    consecutive += 1
                else:
                    break

            _state["consecutive_losses"] = consecutive
            restored["consecutive_losses"] = consecutive

            summary = (
                f"Risk state restored — Peak: ₹{peak:.0f} | P&L today: ₹{realized_pnl:+.0f} | "
                f"RiskStop: {_state['risk_stop_active']} | KillLine: {_state['kill_line_active']} | "
                f"ConsecLoss: {consecutive}"
            )
            logger.info(f"[Restore] {summary}")

            try:
                insert_system_log("RISK_STATE_RESTORE", summary, level="INFO", system_mode=sys_mode)
            except Exception:
                pass

            return restored
        except Exception as e:
            logger.exception(f"[Restore] restore_risk_state failed: {e}")
            return {}


def reset_daily_state() -> None:
    """
    Reset daily risk triggers at start of new trading day (08:25 AM IST).
    Risk Stop, Soft Stop, and Flash Crash resets. 15% Kill Line requires manual reset.
    """
    with _RISK_LOCK:
        _state["consecutive_losses"] = 0
        _equity_history.clear()

        # Re-anchor the session peak to TODAY'S baseline so kill-line
        # drawdown measures today's damage from this morning's open,
        # not a stale lifetime watermark.
        try:
            _state["peak_equity"] = _session_baseline_equity(str(SYSTEM_MODE).upper())
            _state["peak_session_date"] = str(today_ist())
        except Exception:
            pass

        # Reset Risk Stop
        if _state["risk_stop_active"]:
            _state["risk_stop_active"] = False
            logger.info("Daily reset — Risk Stop cleared for new trading day.")
            _safe_send_telegram(
                "✅ <b>MJONAI</b> — New trading day.\n"
                "Risk Stop cleared. System ready for signals."
            )

        # Auto-clear manual pause
        if _state["manual_pause_active"]:
            _state["manual_pause_active"] = False
            _state["manual_pause_reason"] = None
            logger.info("Manual pause auto-cleared at daily reset.")
            _safe_send_telegram(
                "🔄 <b>MJONAI</b> — Manual pause from previous session cleared.\n"
                "System ready for signal generation.\n"
                "Send /pause again if needed."
            )

        # Reset Soft Stop and Flash Crash
        _state["soft_stop_active"] = False
        _state["soft_stop_until"] = None
        _state["flash_crash_pause_active"] = False
        _state["flash_crash_until"] = None


# ── 4. MANUAL REMOTE PAUSE / RESUME ──────────────────────────────────────────

def set_manual_pause(reason: str = "Manual pause by MJ Reddy") -> None:
    """Activate manual pause via Telegram /pause command."""
    clean_reason = (reason or "Manual pause").strip()
    with _RISK_LOCK:
        _state["manual_pause_active"] = True
        _state["manual_pause_reason"] = clean_reason
        logger.warning(f"[EmergencyTriggers] Manual pause activated: {clean_reason}")


def clear_manual_pause() -> None:
    """Lift manual pause via Telegram /resume command."""
    with _RISK_LOCK:
        if not _state["manual_pause_active"]:
            return
        _state["manual_pause_active"] = False
        _state["manual_pause_reason"] = None
        logger.info("[EmergencyTriggers] Manual pause cleared.")


# ── 5. MASTER TRADING CLEARANCE GATE ─────────────────────────────────────────

def is_trading_allowed(system_mode: Optional[str] = None) -> bool:
    """
    Returns True only if no emergency trigger, kill line, or behavioral cooldown is active.
    """
    status = get_emergency_risk_status(system_mode=system_mode)
    return status.trading_allowed


def get_emergency_risk_status(
    live_prices: Optional[dict] = None,
    symbol_map: Optional[dict] = None,
    system_mode: Optional[str] = None,
) -> EmergencyRiskStatus:
    """
    Return comprehensive structured status of all portfolio risk sentries.
    """
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    now = now_ist()
    reasons: List[str] = []

    with _RISK_LOCK:
        # 1. 15% Kill Line Check
        if _state["kill_line_active"]:
            if sys_mode != "RESEARCH":
                reasons.append("Kill line active (>= 15% drawdown) — all trading blocked.")

        # 2. Daily Risk Stop Check
        if _state["risk_stop_active"]:
            reasons.append("Daily Risk Stop active (>= 3.0% loss) — signals blocked for today.")

        # 3. Manual Pause Check
        if _state["manual_pause_active"]:
            reasons.append(f"Manual pause active: {_state['manual_pause_reason']}")

        # 4. Flash-Crash Velocity Sentry Check
        if _state["flash_crash_pause_active"]:
            if _state["flash_crash_until"] and now > _state["flash_crash_until"]:
                _state["flash_crash_pause_active"] = False
                _state["flash_crash_until"] = None
                logger.info("[EmergencyTriggers] Flash-crash pause expired — trading resumed.")
            else:
                rem_mins = int((_state["flash_crash_until"] - now).total_seconds() / 60) if _state["flash_crash_until"] else 0
                reasons.append(f"Flash-Crash protection active ({rem_mins}m remaining).")

        # 5. Soft Stop Check
        if _state["soft_stop_active"]:
            if sys_mode == "RESEARCH":
                _state["soft_stop_active"] = False
                _state["soft_stop_until"] = None
            elif _state["soft_stop_until"] and now > _state["soft_stop_until"]:
                _state["soft_stop_active"] = False
                _state["soft_stop_until"] = None
                logger.info("[EmergencyTriggers] Soft stop lifted automatically.")
                _safe_send_telegram("✅ <b>MJONAI</b> — Soft stop lifted. Signal generation resumed.")
            else:
                rem_mins = int((_state["soft_stop_until"] - now).total_seconds() / 60) if _state["soft_stop_until"] else 0
                reasons.append(f"Soft stop active ({rem_mins}m remaining).")

        # 6. Behavioral Guard Integration
        try:
            from mjonai.risk.behavioral_guard import check_behavioral_guard
            b_allowed, b_reason = check_behavioral_guard(0, system_mode=sys_mode)
            if not b_allowed and sys_mode != "RESEARCH":
                reasons.append(f"Behavioral guard: {b_reason}")
        except Exception as e:
            logger.error(f"[EmergencyTriggers] Behavioral guard check error: {e}")
            if sys_mode != "RESEARCH":
                # F14: an unevaluable psychology guard must BLOCK trading fail-closed in LIVE/PAPER,
                # not let trading through (the old except only logged and returned trading_allowed=True).
                reasons.append("Behavioral guard evaluation failed — trading blocked fail-closed.")

        # Compute P&L Metrics (baseline-anchored, see _session_baseline_equity)
        baseline = _session_baseline_equity(sys_mode)
        peak = _safe_float(_state.get("peak_equity"), default=baseline)
        realized_pnl = 0.0
        unrealized_pnl = 0.0
        # P1-RISK-1: an unevaluable P&L must BLOCK trading fail-closed, not
        # read as "no loss". The old except-pass left both legs at 0.0, so a
        # broken DB/price feed reported daily_loss_pct = 0.0% and permitted
        # new orders while the infrastructure was blind.
        pnl_blind = False
        try:
            from mjonai.db.repository import get_trades_closed_today
            closed_today = get_trades_closed_today(system_mode=sys_mode) or []
            realized_pnl = sum(_safe_float(t.get("net_pnl")) for t in closed_today)
        except Exception:
            pnl_blind = True

        try:
            from mjonai.execution.paper import get_open_trades_with_pnl
            open_trades = get_open_trades_with_pnl(live_prices, symbol_map) or []
            unrealized_pnl = sum(_safe_float(t.get("pnl")) for t in open_trades)
        except Exception:
            pnl_blind = True

        if pnl_blind and sys_mode != "RESEARCH":
            reasons.append("P&L evaluation failed (DB/price feed) — trading blocked fail-closed.")

        total_pnl = realized_pnl + unrealized_pnl
        baseline = _session_baseline_equity(sys_mode)
        current_equity = baseline + total_pnl
        daily_loss_pct = (abs(total_pnl) / baseline * 100.0) if (total_pnl < 0 and baseline > 0) else 0.0
        drawdown_pct = ((peak - current_equity) / peak * 100.0) if peak > 0 else 0.0

        trading_allowed = len(reasons) == 0

        return EmergencyRiskStatus(
            trading_allowed=trading_allowed,
            kill_line_active=_state["kill_line_active"],
            risk_stop_active=_state["risk_stop_active"],
            soft_stop_active=_state["soft_stop_active"],
            manual_pause_active=_state["manual_pause_active"],
            flash_crash_pause_active=_state["flash_crash_pause_active"],
            current_drawdown_pct=round(max(0.0, drawdown_pct), 2),
            daily_loss_pct=round(daily_loss_pct, 2),
            peak_equity=round(peak, 2),
            current_equity=round(current_equity, 2),
            realized_pnl_today=round(realized_pnl, 2),
            unrealized_pnl=round(unrealized_pnl, 2),
            total_pnl_today=round(total_pnl, 2),
            reasons=reasons,
        )


# ── 6. REAL-TIME MTM MONITORING & VELOCITY SENTRIES ──────────────────────────

def _session_baseline_equity(sys_mode: str) -> float:
    """
    Equity baseline for TODAY: yesterday's closing capital from the
    daily snapshot chain (fallback: configured TOTAL_CAPITAL).

    The old kill-line math compared a lifetime peak watermark against
    TOTAL_CAPITAL + today-only P&L — after any profitable history every
    morning read as phantom drawdown, and true ruin could hide if the
    capital constant went stale.
    """
    try:
        from mjonai.db.repository import get_latest_snapshot_before
        snap = get_latest_snapshot_before(sys_mode, str(today_ist()))
        if snap and snap.get("capital_total") is not None:
            val = _safe_float(snap.get("capital_total"), default=0.0)
            if val > 0:
                return val
    except Exception as e:
        logger.debug(f"[EmergencyTriggers] baseline snapshot unavailable: {e}")
    return _safe_float(TOTAL_CAPITAL, default=200000.0)



def update_consecutive_losses(outcome: str, symbol: str = "", system_mode: Optional[str] = None, exit_reason: str = "") -> None:
    """
    Update consecutive loss counter and fire Soft Stop if threshold is hit.

    system_mode defaults to None so the LIVE/RESEARCH decision resolves
    from SYSTEM_MODE config. The old hard default "RESEARCH" shadowed the
    `or SYSTEM_MODE` fallback entirely, making the Soft Stop unreachable
    in LIVE mode (it logged 'would stop' forever).
    """
    outcome_clean = str(outcome or "").strip().upper()
    sys_mode = str(system_mode or SYSTEM_MODE).upper()

    with _RISK_LOCK:
        # Record in behavioral guard
        try:
            from mjonai.risk.behavioral_guard import record_trade_outcome
            record_trade_outcome(outcome_clean, symbol=symbol, system_mode=sys_mode, exit_reason=exit_reason)
        except Exception:
            pass

        if outcome_clean == "LOSS":
            _state["consecutive_losses"] += 1
            logger.info(f"[EmergencyTriggers] Consecutive losses: {_state['consecutive_losses']}/{CONSECUTIVE_LOSS_LIMIT}")
            _check_soft_stop(system_mode=sys_mode)
        elif outcome_clean == "WIN":
            _state["consecutive_losses"] = 0


def _check_soft_stop(system_mode: Optional[str] = None) -> None:
    """Fire Soft Stop (SOFT_STOP_DURATION_MINUTES pause) after 3 consecutive losses."""
    sys_mode_resolved = str(system_mode or SYSTEM_MODE).upper()
    system_mode = sys_mode_resolved
    if _state["consecutive_losses"] >= CONSECUTIVE_LOSS_LIMIT and not _state["soft_stop_active"]:
        if system_mode == "RESEARCH":
            msg = (
                f"⚠️ <b>MJONAI RESEARCH — Would Soft Stop</b>\n"
                f"Trigger: {CONSECUTIVE_LOSS_LIMIT} consecutive losses\n"
                f"Action: <b>None</b> (RESEARCH mode — signals continue)\n"
                f"Logging for analysis only."
            )
            _safe_send_telegram(msg)
            logger.warning(f"[RESEARCH] RESEARCH_WOULD_STOP — {_state['consecutive_losses']} consecutive losses.")
            _log_risk_event("RESEARCH_WOULD_STOP", f"{CONSECUTIVE_LOSS_LIMIT} consecutive losses in RESEARCH mode", system_mode=system_mode)
            return

        _state["soft_stop_active"] = True
        _state["soft_stop_until"] = now_ist() + timedelta(minutes=SOFT_STOP_DURATION_MINUTES)

        msg = (
            f"⚠️ <b>MJONAI — SOFT STOP</b>\n"
            f"Trigger: {CONSECUTIVE_LOSS_LIMIT} consecutive losses\n"
            f"Action: New signals paused for {SOFT_STOP_DURATION_MINUTES} minutes\n"
            f"Resumes: {_state['soft_stop_until'].strftime('%H:%M IST')}\n"
            f"Open trades continue to be monitored."
        )
        _safe_send_telegram(msg)
        logger.warning(f"SOFT STOP activated — {CONSECUTIVE_LOSS_LIMIT} consecutive losses.")
        _log_risk_event("SOFT_STOP", f"{CONSECUTIVE_LOSS_LIMIT} consecutive losses", system_mode=system_mode)


def check_daily_loss(
    live_prices: Optional[dict] = None,
    symbol_map: Optional[dict] = None,
    system_mode: Optional[str] = None,
) -> None:
    """
    Calculate today's realized + unrealized P&L and check Flash-Crash velocity,
    Risk Stop (3%), and the 15% Kill Line (session + lifetime circuits).
    Called every minute from main.py. Kill Line and lifetime peak are handled
    only in non-RESEARCH modes (LIVE + PAPER); RESEARCH never arms or updates
    the lifetime watermark.
    """
    sys_mode = str(system_mode or SYSTEM_MODE).upper()
    now = now_ist()

    with _RISK_LOCK:
        try:
            from mjonai.execution.paper import get_open_trades_with_pnl
            from mjonai.db.repository import get_trades_closed_today, save_peak_equity, load_peak_equity

            # 1. Realized P&L
            closed = get_trades_closed_today(system_mode=sys_mode) or []
            realized_pnl = sum(_safe_float(t.get("net_pnl")) for t in closed)

            # 2. Unrealized P&L
            open_trades = get_open_trades_with_pnl(live_prices, symbol_map) or []
            unrealized_pnl = sum(_safe_float(t.get("pnl")) for t in open_trades)

            total_pnl = realized_pnl + unrealized_pnl
            baseline = _session_baseline_equity(sys_mode)
            current_equity = baseline + total_pnl
            loss_pct = (abs(total_pnl) / baseline * 100.0) if (total_pnl < 0 and baseline > 0) else 0.0

            # 3. SESSION-anchored peak: resets each calendar day to the
            # daily baseline. Kill-line now measures today's damage from
            # yesterday's close — coherent with today-only P&L inputs.
            _today_iso = str(today_ist())
            if _state.get("peak_session_date") != _today_iso:
                _state["peak_session_date"] = _today_iso
                _state["peak_equity"] = max(baseline, current_equity)
            elif current_equity > _state["peak_equity"]:
                _state["peak_equity"] = current_equity

            # 4. Flash-Crash Velocity Sentry (Drop > 1.5% in < 5 mins)
            _equity_history.append((now, current_equity))
            # Clean entries older than 5 minutes
            cutoff_time = now - timedelta(minutes=5)
            while _equity_history and _equity_history[0][0] < cutoff_time:
                _equity_history.pop(0)

            if len(_equity_history) >= 2:
                five_min_ago_equity = _equity_history[0][1]
                rapid_drop_pct = ((five_min_ago_equity - current_equity) / five_min_ago_equity) * 100.0
                if rapid_drop_pct >= 1.5 and not _state["flash_crash_pause_active"]:
                    _state["flash_crash_pause_active"] = True
                    _state["flash_crash_until"] = now + timedelta(minutes=15)
                    fc_msg = (
                        f"⚡ <b>MJONAI — FLASH-CRASH SENTRY TRIGGERED</b>\n"
                        f"Velocity: Equity dropped {rapid_drop_pct:.1f}% in < 5 minutes.\n"
                        f"Action: New entries paused for 15 minutes to allow market to settle."
                    )
                    _safe_send_telegram(fc_msg)
                    logger.critical(f"[EmergencyTriggers] FLASH-CRASH PAUSE FIRED: {rapid_drop_pct:.1f}% drop in 5m.")
                    _log_risk_event("FLASH_CRASH_PAUSE", f"Rapid drop {rapid_drop_pct:.1f}% in 5m", system_mode=sys_mode)

            # 5. Kill Line Check (P0.6 ruling 2026-09-20) — TWO independent circuits,
            # both measured in non-RESEARCH modes (LIVE + PAPER):
            #   (a) SESSION circuit: drawdown from the session peak anchored to
            #       yesterday's close each morning (today's damage).
            #   (b) LIFETIME ruin protection: equity <= (100 - KILL_LINE_PCT)% of the
            #       persisted lifetime peak watermark (`save_peak_equity`/`load_peak_equity`,
            #       monotonic, manual-reset only). No longer fiction — implemented here.
            # Fire if EITHER circuit breaches the 15% line.
            session_peak = _safe_float(_state.get("peak_equity"), default=baseline)
            session_drawdown_pct = (
                (session_peak - current_equity) / session_peak * 100.0
                if session_peak > 0
                else 0.0
            )

            # Lifetime peak is only maintained/read in non-RESEARCH modes:
            # exploratory RESEARCH equity must never advance the persisted
            # watermark or spuriously trip the lifetime circuit.
            lifetime_drawdown_pct = 0.0
            if sys_mode != "RESEARCH":
                lifetime_peak = load_peak_equity(default=TOTAL_CAPITAL)
                if current_equity > lifetime_peak:
                    save_peak_equity(current_equity)
                    lifetime_peak = current_equity
                lifetime_drawdown_pct = (
                    (lifetime_peak - current_equity) / lifetime_peak * 100.0
                    if lifetime_peak > 0
                    else 0.0
                )

            effective_drawdown_pct = max(session_drawdown_pct, lifetime_drawdown_pct)

            if (
                sys_mode != "RESEARCH"
                and effective_drawdown_pct >= KILL_LINE_PCT
                and not _state["kill_line_active"]
            ):
                _fire_kill_line(effective_drawdown_pct, total_pnl, system_mode=sys_mode)
                return

            # 6. Daily Risk Stop Check (3%)
            if loss_pct >= DAILY_LOSS_LIMIT_PCT and not _state["risk_stop_active"]:
                _fire_risk_stop(loss_pct, total_pnl, system_mode=sys_mode)

        except Exception as e:
            logger.exception(f"[EmergencyTriggers] check_daily_loss failed: {e}")


def _fire_risk_stop(loss_pct: float, total_pnl: float, system_mode: str = "RESEARCH") -> None:
    """Activate Risk Stop — daily loss limit breached."""
    if _state["risk_stop_active"]:
        return

    _state["risk_stop_active"] = True

    msg = (
        f"🛑 <b>MJONAI — RISK STOP</b>\n"
        f"Trigger: Daily loss {loss_pct:.1f}% >= {DAILY_LOSS_LIMIT_PCT}% limit\n"
        f"Total P&L today: ₹{total_pnl:+.0f}\n"
        f"Action: All new signals blocked\n"
        f"Resumes: Tomorrow 8:25 AM IST (daily reset)\n"
        f"Open trades continue to be monitored."
    )
    _safe_send_telegram(msg)
    logger.critical(f"RISK STOP fired — daily loss {loss_pct:.1f}%")
    _log_risk_event("RISK_STOP", f"Daily loss {loss_pct:.1f}%", level="EMERGENCY", system_mode=system_mode)


def _fire_kill_line(drawdown_pct: float, total_pnl: float, system_mode: str = "RESEARCH") -> None:
    """Activate Kill Line — 15% portfolio drawdown breached."""
    if _state["kill_line_active"]:
        return

    _state["kill_line_active"] = True

    # Auto-close all paper/live positions immediately
    try:
        from mjonai.execution.paper import close_all_paper_trades
        # Regression pin (2026-09-03 audit): the old call used reason=,
        # which close_all_paper_trades(exit_reason=...) does not accept —
        # a 100% TypeError swallowed by the except branch, so the Kill
        # Line never auto-closed a single position.
        result = close_all_paper_trades(exit_reason="KILL_LINE") or {}
        closed = int(result.get("closed", 0))
        left = [str(s) for s in (result.get("left_open") or [])]
        if left:
            close_msg = (f"{closed} position(s) closed automatically. "
                         f"STILL OPEN (stale feed, close manually): {', '.join(left)}.")
        else:
            close_msg = f"All {closed} paper position(s) closed automatically. Book flat."
    except Exception:
        logger.exception("Auto-close failed.")
        close_msg = "⚠️ Auto-close failed. Close positions manually in AngelOne."

    msg = (
        f"🚨 <b>MJONAI — KILL LINE HIT</b>\n"
        f"Drawdown: {drawdown_pct:.1f}% from peak equity\n"
        f"Total P&L: ₹{total_pnl:+.0f}\n"
        f"Action: System locked — manual reset required\n"
        f"{close_msg}\n"
        f"Do not resume until root cause is identified."
    )
    _safe_send_telegram(msg)
    logger.critical(f"KILL LINE fired — drawdown {drawdown_pct:.1f}%")
    _log_risk_event("KILL_LINE", f"Drawdown {drawdown_pct:.1f}% from peak", level="EMERGENCY", system_mode=system_mode)
