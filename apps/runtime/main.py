"""
Module: main.py
Purpose: SOTA Master System Runtime Coordinator for MJONAI.
         Orchestrates Pre-Flight Verification, Broker Session Authentication,
         Continuous WebSocket Feeds, Master Scheduler, Multi-Strategy Scanners,
         2-Round Multi-Agent AI Deliberations, and Unified Multi-Channel Broadcasts.
"""

# ADR-0008: repo-root bootstrap — allows `python <this file>` from the repo root.
import sys as _boot_sys
from pathlib import Path as _boot_Path
_BOOT_ROOT = _boot_Path(__file__).resolve().parents[2]
if str(_BOOT_ROOT) not in _boot_sys.path:
    _boot_sys.path.insert(0, str(_BOOT_ROOT))

from datetime import datetime
import logging
import os
import sys
import time
from typing import Dict, List, Any, Optional

from mjonai.core.runtime_config import load_mjonai_env
load_mjonai_env()

# Force process timezone to Indian Standard Time (IST)
os.environ["TZ"] = "Asia/Kolkata"
if hasattr(time, "tzset"):
    time.tzset()

# Configure standardized logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("MJONAI")

from mjonai.core.time_utils import is_trading_day, is_market_open, now_ist
from mjonai.core.market_state import get_market_state
from mjonai.core.mqi import calculate_mqi
from mjonai.core.constants import SYSTEM_MODE, TOTAL_CAPITAL, ACTIVE_STRATEGIES
from mjonai.core.runtime_config import (
    SCHEDULER_LOOP_SLEEP_SECONDS,
    ANGELONE_MAX_RETRIES,
    ANGELONE_RETRY_DELAY_SECONDS,
)

from apps.runtime.orchestration.startup import startup_health_check, StartupHealthReport
from apps.runtime.orchestration.health_monitor import collect_health_log
from apps.runtime.orchestration.websocket_supervisor import handle_websocket_health
from apps.runtime.orchestration.scheduler_setup import setup_scheduler, _get_scheduler
from apps.runtime.orchestration.runtime_guard import cleanup, register_runtime_guard
from apps.runtime.orchestration.market_session_lifecycle import get_current_session_state, MarketSessionState
from apps.runtime.orchestration.heartbeat_sentry import emit_heartbeat
from apps.runtime.orchestration.process_watchdog import GLOBAL_WATCHDOG

from mjonai.communication.dispatcher import (
    broadcast_signal,
    broadcast_trade_closed,
    broadcast_emergency,
    broadcast_pre_market,
    broadcast_eod,
    broadcast_market_state,
)
from mjonai.communication.telegram import send_message, send_mqi_alert
from mjonai.communication.telegram_commands import start_command_listener
from mjonai.communication.events import publish_event

from mjonai.data.angelone.websocket import (
    set_auth,
    start_websocket,
    stop_websocket,
    live_prices,
    is_websocket_healthy,
)
from mjonai.data.angelone.token_map import SYMBOL_MAP, WATCHLIST_TOKENS
from mjonai.data.macro.macro_check import fetch_macro_sentiment
from mjonai.risk.emergency_triggers import check_daily_loss, is_trading_allowed, reset_daily_state

# Global Angel One session
angel_obj: Optional[Any] = None

# Daily signal capacity
_signals_allowed_today: Optional[int] = None


def _login_and_set_auth(max_retries: int = ANGELONE_MAX_RETRIES) -> bool:
    """
    TOTP login ONLY: refreshes auth/feed tokens via set_auth().
    Does NOT touch socket lifecycle — the websocket reconnect loop owns
    restarts (C8b: lets it pick up fresh tokens mid-recovery instead of
    reusing startup-era credentials that died at the daily rollover).
    """
    global angel_obj

    try:
        import pyotp
        from SmartApi import SmartConnect
    except ImportError:
        logger.warning("[Broker] SmartApi/pyotp packages not found. Operating in Paper/Research mode.")
        return False

    for attempt in range(1, max_retries + 1):
        try:
            logger.info(f"[Broker] Angel One login attempt {attempt}/{max_retries}...")

            totp_secret = os.getenv("ANGELONE_TOTP_SECRET", "")
            totp = pyotp.TOTP(totp_secret).now() if totp_secret else ""
            api_key = os.getenv("ANGELONE_API_KEY", "")
            client_id = os.getenv("ANGELONE_CLIENT_ID", "")
            password = os.getenv("ANGELONE_PASSWORD", "")

            angel_obj = SmartConnect(api_key=api_key)
            raw_data = angel_obj.generateSession(client_id, password, totp)

            if isinstance(raw_data, dict) and raw_data.get("status"):
                data_dict = raw_data.get("data")
                auth_token = str(data_dict.get("jwtToken") if isinstance(data_dict, dict) else "")
                feed_token = str(angel_obj.getfeedToken() or "")

                if auth_token and feed_token:
                    logger.info(f"✅ Angel One login OK — Client ID: {client_id}")
                    set_auth(auth_token, feed_token, client_id)
                    return True
            else:
                msg = raw_data.get("message", "Unknown error") if isinstance(raw_data, dict) else "Non-dict response"
                logger.warning(f"❌ Attempt {attempt} failed: {msg}")
                if attempt < max_retries:
                    time.sleep(ANGELONE_RETRY_DELAY_SECONDS)

        except Exception as e:
            logger.error(f"❌ Attempt {attempt} exception: {e}")
            if attempt < max_retries:
                time.sleep(ANGELONE_RETRY_DELAY_SECONDS)

    return False


def connect_angelone() -> bool:
    """Full broker connect: TOTP login + (re)start of the live feed socket.
    Used at startup and by the scheduled 08:25 pre-market job."""
    ok = _login_and_set_auth()
    if not ok:
        logger.warning(f"⚠️ Angel One SmartAPI login failed — falling back to paper simulation feeds.")
        return False

    logger.info(f"✅ Connected to Angel One SmartAPI (Mode: {SYSTEM_MODE}) — Starting Live WebSocket Stream...")
    stop_websocket()

    # Collect open option tokens from database to stream alongside cash equities
    startup_tokens = [WATCHLIST_TOKENS]
    try:
        from mjonai.db.repository import get_open_trades
        from mjonai.data.angelone.token_map import get_token_for_symbol
        open_pos = get_open_trades() or []
        opt_tokens = []
        for p in open_pos:
            sym = str(p.get("symbol", "")).upper()
            if sym.endswith("CE") or sym.endswith("PE"):
                tok = get_token_for_symbol(sym)
                if tok:
                    opt_tokens.append(tok)
        if opt_tokens:
            startup_tokens.append({"exchangeType": 2, "tokens": list(set(opt_tokens))})
            logger.info(f"[Broker] Added {len(set(opt_tokens))} open option token(s) to live WebSocket subscription.")
    except Exception as e:
        logger.warning(f"[Broker] Could not load open option tokens for WebSocket: {e}")

    start_websocket(startup_tokens)
    return True


def monitor_trades() -> None:
    """
    Continuous 1-minute execution monitor:
    - Verifies WebSocket tick feed liveness
    - Evaluates open positions for Trailing SL ratchets, Breakeven triggers, and Tranche targets
    - Checks daily loss thresholds and emergency kill lines
    - Emits telemetry logs
    """
    if not is_market_open():
        return

    try:
        from mjonai.execution.paper import check_paper_trades
        from mjonai.db.repository import get_open_trades

        ws_healthy = is_websocket_healthy()
        handle_websocket_health(ws_healthy)

        # Check trailing SL and tranche target hits
        closed_trades = check_paper_trades(live_prices, SYMBOL_MAP)

        if closed_trades:
            from mjonai.risk.emergency_triggers import update_consecutive_losses

            for trade in closed_trades:
                pnl = float(trade.get("pnl") or trade.get("net_pnl") or trade.get("realized_pnl") or 0.0)
                outcome = "WIN" if pnl > 0 else "LOSS"
                trade_symbol = str(trade.get("symbol") or "")
                update_consecutive_losses(outcome, symbol=trade_symbol, system_mode=SYSTEM_MODE)
                broadcast_trade_closed(trade)

                # Post-trade AI reflection
                try:
                    from mjonai.agents.critic import reflect_on_closed_trade
                    reflection = reflect_on_closed_trade(trade)
                    quality = reflection.get("execution_quality", "EVALUATED")
                    logger.info(f"[Critic] Trade #{trade.get('id')} classified as {quality}")
                except Exception as e:
                    logger.debug(f"[Critic] Post-trade reflection notice: {e}")

        # Check daily drawdown boundaries
        check_daily_loss(live_prices, SYMBOL_MAP)

        # Record minute telemetry
        open_trades = get_open_trades()
        live_count = len(live_prices) if live_prices else 0

        collect_health_log(
            websocket_healthy=ws_healthy,
            angelone_connected=(angel_obj is not None or SYSTEM_MODE != "LIVE"),
            live_prices_count=live_count,
            stale_symbols=0,
            active_trades=len(open_trades),
        )

    except Exception as e:
        logger.error(f"[Monitor] Execution loop error: {e}", exc_info=True)


def morning_routine() -> None:
    """
    08:30 AM Pre-Market Macro Intelligence Routine:
    - Evaluates Market Regime (BULL, BEAR, RANGE_BOUND) & India VIX
    - Computes Market Quality Index (MQI)
    - Integrates Global Macro sentiment (S&P 500, Crude, DXY)
    - Dispatches multi-channel briefings
    """
    if not is_trading_day():
        logger.info(f"[{now_ist().strftime('%H:%M')}] Non-trading day — system resting.")
        return

    logger.info("=" * 65)
    logger.info(f"  🌅 MJONAI PRE-MARKET BRIEFING — {now_ist().strftime('%d %b %Y %H:%M IST')}")
    logger.info("=" * 65)

    try:
        # Step 1: Market State & India VIX
        market_state, total_score, vix, high_vol_override = get_market_state()
        broadcast_market_state(market_state, total_score, vix)

        if high_vol_override:
            send_message(
                f"🚨 <b>HIGH VOLATILITY OVERRIDE</b>\n"
                f"India VIX: <b>{vix:.2f}</b> (> 25.0 threshold).\n"
                f"New position entries blocked for today. Existing trades monitored."
            )

        # Step 2: MQI Calculation
        mqi_level, signals_allowed, no_trade, mqi_score = calculate_mqi()
        send_mqi_alert(mqi_level, mqi_score, signals_allowed, no_trade)

        # Step 3: Global Macro Sentiment Check
        macro = fetch_macro_sentiment()
        logger.info(
            f"  Macro Data — S&P 500: {macro['sp500_change_pct']:+.2f}% | "
            f"Crude: {macro['crude_change_pct']:+.2f}% | DXY: {macro['dxy_change_pct']:+.2f}%"
        )

        if macro["signal_limit_adjustment"] < 0 and not no_trade:
            signals_allowed = max(0, signals_allowed + macro["signal_limit_adjustment"])
            send_message(f"⚠️ <b>Macro Adjustment</b>: {macro['flags'][0] if macro['flags'] else 'Restricted'}")

        global _signals_allowed_today
        if SYSTEM_MODE == "RESEARCH":
            _signals_allowed_today = 9999
        else:
            _signals_allowed_today = signals_allowed if not no_trade else 0

        # Step 4: Multi-Channel Pre-Market Dispatch
        broadcast_pre_market(
            gap_data={"market_state": market_state, "vix": vix},
            fii_data={"mqi_score": mqi_score, "mqi_level": mqi_level},
            sector_data={"signals_allowed": _signals_allowed_today, "no_trade": no_trade},
        )

        logger.info(f"✅ Morning routine complete — Signals allowed today: {_signals_allowed_today}")

    except Exception as e:
        logger.error(f"[Morning Routine] Error: {e}", exc_info=True)
        send_message(f"❌ <b>MJONAI MORNING ERROR</b>\n{str(e)}")


def _get_signals_allowed(mqi_level: str) -> int:
    """Derive signal allocation from MQI level."""
    if SYSTEM_MODE == "RESEARCH":
        return 9999
    mapping = {"HIGH": 2, "MEDIUM": 1, "LOW": 1, "VERY LOW": 0}
    return mapping.get(mqi_level, 1)


def scan_and_execute() -> None:
    """
    Intraday 15-Minute Strategy Scanner & Multi-Agent Deliberation Pipeline:
    - Time Gate: 09:30 AM to 03:15 PM IST
    - Scans S01-S12 strategy candidates
    - Submits setups to 2-Round Bull/Bear Adversarial Debate
    - Evaluates consensus conviction scores
    - Executes approved trades and fans out alerts
    """
    if not is_trading_day():
        return

    now = now_ist()
    start_ok = (now.hour == 9 and now.minute >= 30) or (now.hour >= 10)
    end_ok = (now.hour < 15) or (now.hour == 15 and now.minute <= 15)

    if not start_ok or not end_ok:
        return

    logger.info(f"[Scanner] Running 15-minute scan at {now.strftime('%H:%M IST')}...")

    try:
        # Gate 1: Risk Engine Sentry
        if not is_trading_allowed():
            logger.info("[Scanner] Blocked — Daily Risk Stop or Lifetime Kill Line active.")
            return

        # Gate 2: Market State from Database
        from mjonai.db.repository import get_latest_market_state, get_signals_intelligence_today

        state = get_latest_market_state() or {}
        if state.get("no_trade_day") and SYSTEM_MODE != "RESEARCH":
            logger.info("[Scanner] Blocked — No Trade Day active.")
            return

        if state.get("high_vol_override") and SYSTEM_MODE != "RESEARCH":
            logger.info("[Scanner] Blocked — High Volatility Override active.")
            return

        # Gate 3: Capacity Limit Check
        mqi_level = str(state.get("mqi_level") or "HIGH")
        signals_allowed = _signals_allowed_today if _signals_allowed_today is not None else _get_signals_allowed(mqi_level)

        signals_today = get_signals_intelligence_today()
        approved_today = [s for s in signals_today if s.get("signal_type") == "APPROVED"]
        remaining_slots = signals_allowed - len(approved_today)

        if remaining_slots <= 0:
            logger.info(f"[Scanner] Daily limit reached ({len(approved_today)}/{signals_allowed} used).")
            return

        # Gate 4: Live Price Feed Sentry
        if not live_prices and SYSTEM_MODE == "LIVE":
            logger.warning("[Scanner] No live prices received. Skipping scan cycle.")
            return

        market_state_name = str(state.get("market_state") or "NEUTRAL")
        vix_val = float(state.get("vix") or 15.0)

        # Run multi-strategy scan
        from mjonai.strategy.signal_scanner import scan_signals
        candidate_signals = scan_signals(
            mqi_level=mqi_level,
            signals_allowed=remaining_slots,
            market_state=market_state_name,
            vix=vix_val,
            live_prices=live_prices,
            symbol_map=SYMBOL_MAP,
        )

        if not candidate_signals:
            logger.info(f"[Scanner] No candidates approved this cycle at {now.strftime('%H:%M IST')}.")
            return
        # Execute approved trades — route through the unified dispatcher
        # (execution.orders.execute_order) rather than open_paper_trade()
        # directly. RESEARCH/PAPER behavior is identical (execute_order
        # delegates to the paper path); in LIVE mode the repaired
        # ledger-first broker sequence finally becomes reachable.
        from mjonai.execution.orders import execute_order

        for signal in candidate_signals:
            # NOTE (G2/G3): the AI deliberation verdict is BINDING exactly once,
            # inside strategy.pipeline Gate 6 (SUPERVISOR_DEBATE_VETO). This loop
            # previously ran a SECOND adversarial debate per signal — passing a
            # bare bool into conduct_adversarial_debate's devil_checks_passed
            # list parameter (C3 TypeError every cycle, fail-open on the except)
            # while doubling LLM spend (H10). Candidates arriving here are
            # already post-debate; no second opinion runs here anymore.

            # Open position, then broadcast ONLY on success. The pre-G1 code
            # announced every signal to Telegram/Discord even when the
            # order was refused (dedup block, invalid stop) — followers
            # saw fills that never happened.
            try:
                result = execute_order(signal)
                if result.is_success:
                    broadcast_signal(signal)
                else:
                    logger.warning(
                        f"[Scanner] {signal.get('symbol')} execution refused: {result.message}"
                    )
            except Exception as exec_err:
                logger.error(f"[Scanner] execute_order failure for {signal.get('symbol')}: {exec_err}", exc_info=True)

    except Exception as e:
        logger.error(f"[Scanner] Execution error: {e}", exc_info=True)


def eod_routine() -> None:
    """03:35 PM End-Of-Day Routine: Summarizes P&L and dispatches daily performance scorecards."""
    if not is_trading_day():
        return

    logger.info(f"\n[{now_ist().strftime('%H:%M IST')}] Executing EOD Routine...")
    try:
        from mjonai.execution.paper import eod_summary
        summary_result = eod_summary()
        if summary_result:
            broadcast_eod(summary_result)
    except Exception as e:
        logger.error(f"[EOD] Summary error: {e}", exc_info=True)


def _calculate_forward_returns() -> None:
    """04:00 PM: Computes forward return metrics for ML Alpha models."""
    if not is_trading_day():
        return
    try:
        from mjonai.research.forward_returns import (
            compute_forward_returns,
            forward_return_summary,
        )
        stats = compute_forward_returns(limit=1000)
        logger.info(f"[Research] Forward returns: {stats}")
        summary = forward_return_summary()
        logger.info(f"[Research] Forward return summary: {summary}")
    except Exception as e:
        logger.error(f"[Research] Forward returns failed: {e}", exc_info=True)
    try:
        from mjonai.analytics.learning_loop import run_daily_learning_loop
        loop_result = run_daily_learning_loop()
        logger.info(f"[LearningLoop] {loop_result}")
    except Exception as e:
        logger.error(f"[LearningLoop] daily loop failed: {e}", exc_info=True)


def _generate_daily_research_report() -> None:
    """04:30 PM: Compiles and dispatches daily research performance report."""
    if not is_trading_day():
        return
    try:
        from mjonai.db.repository import get_signals_intelligence_today
        signals = get_signals_intelligence_today()
        if not signals:
            return

        strategy_counts: Dict[str, int] = {}
        for sig in signals:
            sid = sig.get("strategy_id", "UNKNOWN")
            strategy_counts[sid] = strategy_counts.get(sid, 0) + 1

        msg = f"📊 <b>MJONAI Daily Research Summary</b>\n"
        msg += f"📅 {now_ist().strftime('%d %b %Y')}\n\n"
        msg += f"<b>Total Signals Generated:</b> {len(signals)}\n\n"
        msg += "<b>Distribution by Strategy:</b>\n"
        for sid, count in sorted(strategy_counts.items(), key=lambda x: x[1], reverse=True):
            msg += f"  • {sid}: {count}\n"

        send_message(msg)
    except Exception as e:
        logger.error(f"[Research] Daily research report error: {e}")


def _generate_weekly_alphalens_report() -> None:
    """Sunday 10:00 AM: Generates weekly multi-factor Information Coefficient (IC) report."""
    logger.info("[Research] Weekly Alphalens report not implemented — IC analysis does not exist yet; do not cite IC before it is built.")


def main() -> None:
    """Master Application Entry Point."""
    logger.info("=" * 65)
    logger.info(f"  🚀 MJONAI MASTER RUNTIME ONLINE [{SYSTEM_MODE} MODE]")
    logger.info(f"  Started at: {now_ist().strftime('%d %b %Y %H:%M:%S IST')}")
    logger.info("=" * 65)

    # 1. Register main thread signal handlers and atexit teardown hooks
    register_runtime_guard()

    # 2. Run comprehensive pre-flight verification
    health_report: StartupHealthReport = startup_health_check()
    if not health_report.is_ready:
        logger.critical(f"❌ Startup pre-flight health check failed with errors: {health_report.errors}")
        cleanup()
        return

    # 2a. Probe LLM providers: discover working models + validate API keys.
    #     Best-effort — degraded LLM health never blocks engine boot (deterministic
    #     gates + rule-engine fallback keep the system trading either way).
    try:
        from mjonai.agents.llm_bridge import probe_providers, log_provider_health
        llm_health = probe_providers()
        log_provider_health(llm_health)
    except Exception as e:
        logger.warning(f"[LLM] Provider health probe skipped (non-critical): {e}")

    # Recover durable records captured during a previous database outage before
    # normal scheduling creates new state. Each domain is independently best-effort.
    from mjonai.db.repository import replay_all_journals
    replay_results = replay_all_journals()
    recovered = sum(replay_results.values())
    if recovered:
        logger.info("[Database] Recovered %d buffered record(s): %s", recovered, replay_results)

    # 3. Authenticate broker session
    if is_trading_day():
        connect_angelone()
    else:
        logger.info("[Broker] Weekend or exchange holiday — broker login deferred.")

    send_message(
        f"🚀 <b>MJONAI SYSTEM ONLINE</b>\n"
        f"Mode: <b>{SYSTEM_MODE}</b> | Capital: <b>₹{TOTAL_CAPITAL:,.0f}</b>\n"
        f"Started at {now_ist().strftime('%d %b %Y %H:%M IST')}."
    )

    # 4. Start interactive Telegram remote control listener
    try:
        start_command_listener()
    except Exception as e:
        logger.warning(f"[Bot] Telegram command listener warning: {e}")

    # 5. Catch up on late startup if launched mid-morning
    now = now_ist()
    if is_trading_day() and ((now.hour == 8 and now.minute >= 25) or now.hour == 9):
        logger.info(f"[{now.strftime('%H:%M')}] Late launch detected — running morning routine now...")
        morning_routine()

    # 6. Initialize Master Scheduler
    setup_scheduler(
        reset_daily_state=reset_daily_state,
        connect_angelone=connect_angelone,
        morning_routine=morning_routine,
        eod_routine=eod_routine,
        calculate_forward_returns=_calculate_forward_returns,
        generate_daily_report=_generate_daily_research_report,
        generate_weekly_report=_generate_weekly_alphalens_report,
        monitor_trades=monitor_trades,
        scan_and_execute=scan_and_execute,
        is_trading_day=is_trading_day,
    )

    # 6b. C8b: give the websocket reconnect loop a way to obtain FRESH broker
    # tokens (TOTP login only, no socket restart) when repeated reconnect
    # attempts fail — e.g. Angel One's daily token rollover killing the
    # startup-era credentials. No-op in Paper/Research modes.
    from mjonai.data.angelone.websocket import set_reauth_callback
    set_reauth_callback(lambda: _login_and_set_auth())

    logger.info("\n✅ MJONAI operational. Entering main execution loop... (Press Ctrl+C to terminate)\n")

    # 7. Resilient Event Loop
    sch = _get_scheduler()
    last_heartbeat_time = 0.0

    while True:
        try:
            # Periodic Heartbeat & Thread Supervision (~30 seconds cadence)
            loop_now = time.time()
            if loop_now - last_heartbeat_time >= 30.0:
                try:
                    open_trades_count = 0
                    try:
                        from mjonai.db.repository import get_open_trades
                        open_trades_count = len(get_open_trades() or [])
                    except Exception:
                        pass
                    
                    emit_heartbeat(
                        websocket_healthy=is_websocket_healthy(),
                        open_positions_count=open_trades_count,
                    )
                    GLOBAL_WATCHDOG.supervise_workers()
                except Exception as hb_err:
                    logger.warning(f"[Main Loop] Heartbeat error: {hb_err}")
                last_heartbeat_time = loop_now

            # Execute registered scheduler tasks
            if hasattr(sch, "run_pending"):
                sch.run_pending()
            else:
                logger.error("[Scheduler Loop] Scheduler has no run_pending(); jobs will not fire.")
        except KeyboardInterrupt:
            logger.info("\n[Main] Shutdown signal received.")
            break
        except Exception as e:
            logger.error(f"[Scheduler Loop] Exception: {e}", exc_info=True)

        time.sleep(SCHEDULER_LOOP_SLEEP_SECONDS)

    cleanup()


if __name__ == "__main__":
    main()
