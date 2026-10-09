"""
Module: execution/tracker.py
Purpose: SOTA Institutional Active Trade Tracker, Tick-by-Tick MAE/MFE Recording,
         3-Tranche Scaling State Machine, Volatility Trailing Stop Ratchets,
         Time-Barrier Exits, and Real-Time Telegram Event Dispatcher.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
import logging
import time
from typing import Dict, Any, List, Optional, Tuple, Union

from mjonai.core.time_utils import now_ist, today_ist, week_of_month, localize_ist
from mjonai.core.constants import (
    SYSTEM_MODE,
    PAPER_POSITION_SIZE_RESEARCH,
    SECTOR_MAP,
    build_setup_hash,
    get_time_bucket,
)
from mjonai.communication.telegram import send_message
from mjonai.db.repository import (
    get_open_trades,
    get_open_trade_by_symbol,
    get_all_trades_today,
    close_trade,
    get_open_tranches_by_trade,
    close_tranche,
    update_trade_sl,
    update_trade_price_extremes,
    update_trade_research_fields,
    update_trade_exit_fields,
    update_signal_outcome,
)
from mjonai.execution.tax import calculate_tax

logger = logging.getLogger(__name__)

# Holding barriers in calendar days
_MAX_HOLDING_DAYS_INTRADAY = 1
_MAX_HOLDING_DAYS_MEAN_REV = 5
_MAX_HOLDING_DAYS_SWING = 15

# One-alert-per-trade-per-day dedupe for blocked MIS square-offs.
_unsquareable_alerted: Dict[str, Any] = {}


def _get_current_price(
    symbol: str,
    live_prices: Optional[Dict[str, Any]] = None,
    symbol_map: Optional[Dict[str, Any]] = None,
) -> Optional[float]:
    """
    Get current price for a symbol.
    Priority: Feed Manager -> WebSocket LTP -> yfinance fallback -> None.
    """
    try:
        from mjonai.data.feed_manager import get_feed_manager
        fm = get_feed_manager()
        p = fm.get_live_price(symbol)
        if p is not None and float(p) > 0:
            return float(p)
    except Exception:
        pass

    if live_prices is not None and symbol_map is not None:
        token = symbol_map.get(symbol)
        if token:
            # Freshness gate: never serve a raw live_prices entry whose last
            # tick is stale (token stopped ticking while the socket is up).
            price = None
            try:
                from mjonai.data.angelone.websocket import is_token_fresh
                if is_token_fresh(str(token)):
                    price = live_prices.get(str(token))
            except Exception:
                price = None
            if price is not None:
                try:
                    f_price = float(price)
                    if f_price > 0:
                        return f_price
                except (ValueError, TypeError):
                    pass

    clean = symbol.replace(".NS", "").replace(".BO", "").strip().upper()
    if clean.endswith("CE") or clean.endswith("PE") or clean.startswith("TEST_") or "TEST" in clean:
        return None

    # Fallback to yfinance if available
    try:
        import yfinance as yf
        if clean in ("TATAMOTORS", "TATA MOTORS"):
            clean_sym = "TMPV.NS"
        elif clean in ("NIFTY", "NIFTY 50", "NIFTY50"):
            clean_sym = "^NSEI"
        elif clean in ("BANKNIFTY", "NIFTY BANK"):
            clean_sym = "^NSEBANK"
        else:
            clean_sym = f"{clean}.NS" if not symbol.endswith(".NS") and not symbol.endswith(".BO") else symbol
        hist = yf.Ticker(clean_sym).history(period="1d", interval="1m")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass

    return None


def calculate_trailing_sl(
    entry: float,
    current_price: float,
    symbol: str,
    signal_direction: str = "LONG",
    current_sl: Optional[float] = None,
    atr: Optional[float] = None,
    entry_risk: Optional[float] = None,
) -> float:
    """
    Calculate dynamic volatility trailing stop loss candidate.
    Buffer precedence: 2.5*ATR (if ATR supplied) -> entry_risk (the entry-time stop
    distance, which encodes the strategy's ATR/structure sizing and scales with the
    instrument's volatility) -> fallback entry*0.02.
    - Long: max(current_sl, current_price - buffer)
    - Short: min(current_sl, current_price + buffer)
    """
    if atr and atr > 0:
        vol_buf = atr * 2.5
    elif entry_risk and entry_risk > 0:
        vol_buf = entry_risk
    else:
        vol_buf = entry * 0.02
    cur_sl = current_sl if (current_sl and current_sl > 0) else entry

    if str(signal_direction).upper() == "SHORT":
        candidate = round(current_price + vol_buf, 2)
        # Short stop only trails DOWNWARDS (protecting profit)
        return min(cur_sl, candidate)
    else:
        candidate = round(current_price - vol_buf, 2)
        # Long stop only trails UPWARDS (protecting profit)
        return max(cur_sl, candidate)


def update_position_extremes(
    trade_id: Union[int, str],
    current_price: float,
    entry_price: float,
    direction: str = "BUY",
    price_low: Optional[float] = None,
    price_high: Optional[float] = None,
) -> None:
    """Update Maximum Favorable Excursion (MFE) and Maximum Adverse Excursion (MAE)."""
    try:
        update_trade_price_extremes(
            trade_id=str(trade_id),
            current_price=current_price,
            entry_price=entry_price,
            direction=direction,
            price_low_since_entry=price_low,
            price_high_since_entry=price_high,
        )
    except Exception as e:
        logger.warning(f"[Tracker] update_position_extremes error for #{trade_id}: {e}")


def _calculate_holding_days(entry_time_raw: Optional[str]) -> int:
    """Calculate actual trading days held since trade entry (excluding weekends)."""
    if not entry_time_raw:
        return 0
    try:
        import numpy as np
        entry_dt = localize_ist(entry_time_raw)
        now_dt = now_ist()
        if now_dt.date() <= entry_dt.date():
            return 0
        trading_days = np.busday_count(entry_dt.date(), now_dt.date())
        return int(max(0, trading_days))
    except Exception:
        return 0


def evaluate_tranche_exits(
    trade: Dict[str, Any],
    current_price: float,
    send_alerts: bool = True,
    open_tranches: Optional[List[Dict[str, Any]]] = None,
) -> Tuple[bool, List[Dict[str, Any]]]:
    """
    Evaluates 3-tranche scaling exits:
      Tranche 1 (50%): Exits on Target 1, ratchets SL to entry (risk-free).
      Tranche 2 (30%): Exits on Target 2, ratchets SL to Target 1.
      Tranche 3 (20%): Runner trailing with dynamic ATR ratchet stop.
    """
    trade_id = trade.get("id")
    if not trade_id:
        return False, []

    if open_tranches is None:
        open_tranches = get_open_tranches_by_trade(str(trade_id)) or []
    if not open_tranches:
        return False, []

    entry_p = float(trade["entry_price"])
    symbol = str(trade.get("symbol", ""))
    direction = str(trade.get("signal_direction", "LONG")).upper()
    remaining_tranches = list(open_tranches)

    for tr in open_tranches:
        t_num = tr.get("tranche_number")
        t_target = float(tr.get("target_price", 0.0))
        t_qty = int(tr.get("quantity", 0))

        is_target_hit = (current_price >= t_target) if direction == "LONG" else (current_price <= t_target)

        if is_target_hit and t_qty > 0:
            gross_pnl = round((current_price - entry_p) * t_qty, 2) if direction == "LONG" else round((entry_p - current_price) * t_qty, 2)
            tax = calculate_tax(gross_pnl, asset_class=str(trade.get("asset_class") or "EQUITY").upper())
            net_pnl = round(gross_pnl - tax, 2)

            close_tranche(
                tranche_id=str(tr["id"]),
                exit_price=current_price,
                gross_pnl=gross_pnl,
                net_pnl=net_pnl,
            )
            remaining_tranches = [item for item in remaining_tranches if item.get("id") != tr.get("id")]

            parent_raw = trade.get("quantity_remaining")
            parent_qty = int(parent_raw) if parent_raw is not None else int(trade.get("quantity") or 0)
            new_remaining = max(0, parent_qty - t_qty)

            if t_num == 1:
                new_sl = entry_p  # Breakeven SL (100% Risk-Free)
                update_trade_sl(
                    trade_id=str(trade_id),
                    sl_stage="BREAKEVEN",
                    current_sl=new_sl,
                    quantity_remaining=new_remaining,
                )
                msg = f"🎯 <b>Tranche 1 Hit</b>: <code>{symbol}</code> @ ₹{current_price:.2f} (50% closed) — SL moved to Cost (₹{new_sl:.2f}, Risk-Free!)"
                logger.info(f"[Tracker] {msg}")
                if send_alerts:
                    try:
                        send_message(msg)
                    except Exception:
                        pass
            elif t_num == 2:
                new_sl = float(trade.get("target_1", entry_p))
                update_trade_sl(
                    trade_id=str(trade_id),
                    sl_stage="1R_LOCKED",
                    current_sl=new_sl,
                    quantity_remaining=new_remaining,
                )
                msg = f"🎯 <b>Tranche 2 Hit</b>: <code>{symbol}</code> @ ₹{current_price:.2f} (30% closed) — SL locked at Target 1 (₹{new_sl:.2f})"
                logger.info(f"[Tracker] {msg}")
                if send_alerts:
                    try:
                        send_message(msg)
                    except Exception:
                        pass
            else:
                update_trade_sl(
                    trade_id=str(trade_id),
                    sl_stage="TRANCHE_EXIT",
                    current_sl=float(trade.get("current_sl") or trade.get("stop_loss") or entry_p),
                    quantity_remaining=new_remaining,
                )

            return True, remaining_tranches

    return False, remaining_tranches


def check_paper_trades(
    live_prices: Optional[Dict[str, Any]] = None,
    symbol_map: Optional[Dict[str, Any]] = None,
    send_alerts: bool = True,
    system_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Main active position monitoring loop.
    Checks:
      1. MAE / MFE Extremes
      2. 03:15 PM Intraday MIS Square-Off
      3. Stale Trade Time Barriers (5-day Mean Rev / 15-day Swing)
      4. Stop Loss Breach
      5. 3-Tranche Scaling Exits & SL Ratchets
      6. Runner Dynamic ATR Trailing Stops
      7. Final Target Hit
    """
    open_trades = get_open_trades(system_mode=system_mode or SYSTEM_MODE) or []
    if not open_trades:
        return []

    closed_results = []
    current_time_ist = now_ist()
    # Square-off is due from 15:15 ONWARDS (not only within the
    # 15:15-15:59 minute window). The old equality window meant a
    # process restart at 15:05 or a dead tick feed left MIS positions
    # held overnight with no retry and no alert.
    is_eod_squareoff_time = (
        current_time_ist.hour > 15
        or (current_time_ist.hour == 15 and current_time_ist.minute >= 15)
    )

    for trade in open_trades:
        trade_id = trade.get("id")
        if not trade_id:
            continue
        symbol = str(trade.get("symbol", ""))
        direction = str(trade.get("signal_direction", "LONG")).upper()
        timeframe = str(trade.get("timeframe", "SWING")).upper()
        strategy_id = str(trade.get("strategy_id", "")).upper()
        entry_p = float(trade["entry_price"])
        # Direction-aware fallbacks mirror execution/orders.open_paper_trade:
        # the old unconditional LONG-shaped defaults gave a SHORT with NULL
        # stop/target an instant false stop-out (SL below entry) AND an
        # instantly-hit target (above entry).
        if direction == "SHORT":
            default_sl = entry_p * 1.02
            default_target = entry_p * 0.95
        else:
            default_sl = entry_p * 0.98
            default_target = entry_p * 1.05
        cur_sl = float(trade.get("current_sl") or trade.get("stop_loss") or default_sl)
        target = float(trade.get("target") or default_target)
        holding_days = _calculate_holding_days(trade.get("entry_time") or trade.get("created_at"))

        ltp = _get_current_price(symbol, live_prices, symbol_map)
        if ltp is None or ltp <= 0:
            # An intraday position with no price AFTER square-off time
            # is unmanaged overnight risk - say so loudly (once per
            # trade per day), never silently.
            if (
                is_eod_squareoff_time
                and (timeframe == "INTRADAY" or "S08" in strategy_id)
                and trade_id not in _unsquareable_alerted
            ):
                _unsquareable_alerted[str(trade_id)] = current_time_ist.date()
                msg = f"🚨 <b>MIS SQUARE-OFF BLOCKED</b>: <code>{symbol}</code> #{trade_id} has no live price after 15:15 - position held overnight!"
                logger.error(f"[Tracker] {msg}")
                if send_alerts:
                    try:
                        send_message(msg)
                    except Exception:
                        pass
            continue

        # 1. Update MAE/MFE extremes (using in-memory values to eliminate redundant DB calls)
        update_position_extremes(
            trade_id=trade_id,
            current_price=ltp,
            entry_price=entry_p,
            direction=direction,
            price_low=trade.get("price_low_since_entry"),
            price_high=trade.get("price_high_since_entry"),
        )

        # 2. Intraday EOD Square-Off (03:15 PM IST)
        if (timeframe == "INTRADAY" or "S08" in strategy_id) and is_eod_squareoff_time:
            from mjonai.execution.orders import close_paper_trade
            res = close_paper_trade(str(trade_id), exit_price=ltp, exit_reason="INTRADAY_EOD_SQUAREOFF", holding_days=1)
            if res:
                closed_results.append(res)
                if send_alerts:
                    send_message(f"⏰ <b>Intraday Auto-Exit (03:15 PM)</b>: <code>{symbol}</code> closed @ ₹{ltp:.2f}")
            continue

        # 3. Time-Barrier Stale Trade Exit
        max_days = _MAX_HOLDING_DAYS_MEAN_REV if ("S02" in strategy_id or "S06" in strategy_id) else _MAX_HOLDING_DAYS_SWING
        if holding_days > max_days:
            from mjonai.execution.orders import close_paper_trade
            res = close_paper_trade(str(trade_id), exit_price=ltp, exit_reason="TIME_BARRIER_EXPIRED", holding_days=holding_days)
            if res:
                closed_results.append(res)
                if send_alerts:
                    send_message(f"⌛ <b>Time Barrier Exited ({holding_days}d)</b>: <code>{symbol}</code> closed @ ₹{ltp:.2f}")
            continue

        # 4. Check Stop Loss Hit
        is_sl_hit = (ltp <= cur_sl) if direction == "LONG" else (ltp >= cur_sl)
        if is_sl_hit:
            from mjonai.execution.orders import close_paper_trade
            res = close_paper_trade(str(trade_id), exit_price=ltp, exit_reason="STOP_LOSS_HIT", holding_days=holding_days)
            if res:
                closed_results.append(res)
                if send_alerts:
                    send_message(f"🔴 <b>Stop Loss Hit</b>: <code>{symbol}</code> closed @ ₹{ltp:.2f} (SL: ₹{cur_sl:.2f})")
            continue

        # 5. Check Tranche Scaling Exits
        has_tranche_hit, remaining_tranches = evaluate_tranche_exits(trade, ltp, send_alerts=send_alerts)

        # 6. Active Runner Volatility Trailing Stop Ratchet (Reuses remaining_tranches with 0 extra queries)
        if remaining_tranches and all(t.get("tranche_number") == 3 for t in remaining_tranches):
            # Only Runner (Tranche 3) remains open -> trail SL dynamically
            initial_stop = float(trade.get("stop_loss") or 0)
            entry_risk = abs(entry_p - initial_stop) if initial_stop > 0 else None
            new_trailing_sl = calculate_trailing_sl(
                entry=entry_p,
                current_price=ltp,
                symbol=symbol,
                signal_direction=direction,
                current_sl=cur_sl,
                entry_risk=entry_risk,
            )
            if (direction == "LONG" and new_trailing_sl > cur_sl) or (direction == "SHORT" and new_trailing_sl < cur_sl):
                update_trade_sl(
                    trade_id=str(trade_id),
                    sl_stage="TRAILING",
                    current_sl=new_trailing_sl,
                    trailing_sl=new_trailing_sl,
                )
                logger.info(f"[Tracker] 🏃 Runner Trailing SL Ratcheted for {symbol}: ₹{cur_sl:.2f} -> ₹{new_trailing_sl:.2f}")

        # 7. Check Final Target Hit
        is_target_hit = (ltp >= target) if direction == "LONG" else (ltp <= target)
        if is_target_hit:
            from mjonai.execution.orders import close_paper_trade
            res = close_paper_trade(str(trade_id), exit_price=ltp, exit_reason="TARGET_HIT", holding_days=holding_days)
            if res:
                closed_results.append(res)
                if send_alerts:
                    send_message(f"🎉 <b>Final Target Hit</b>: <code>{symbol}</code> closed @ ₹{ltp:.2f} (Target: ₹{target:.2f})")
            continue

    return closed_results


def get_open_trades_with_pnl(
    live_prices: Optional[Dict[str, Any]] = None,
    symbol_map: Optional[Dict[str, Any]] = None,
    system_mode: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Enriches open trades (of the current system mode) with real-time unrealized P&L and ROI."""
    open_trades = get_open_trades(system_mode=system_mode or SYSTEM_MODE) or []
    enriched = []

    for trade in open_trades:
        sym = str(trade.get("symbol", ""))
        entry_p = float(trade["entry_price"])
        qty_raw = trade.get("quantity_remaining")
        qty = int(qty_raw) if qty_raw is not None else int(trade.get("quantity") or 1)
        direction = str(trade.get("signal_direction", "LONG")).upper()

        ltp = _get_current_price(sym, live_prices, symbol_map) or entry_p
        pnl = (ltp - entry_p) * qty if direction == "LONG" else (entry_p - ltp) * qty
        roi_pct = (pnl / (entry_p * qty)) * 100.0 if (entry_p * qty) > 0 else 0.0

        t_copy = dict(trade)
        t_copy["current_price"] = ltp
        t_copy["pnl"] = round(pnl, 2)
        t_copy["roi_pct"] = round(roi_pct, 2)
        enriched.append(t_copy)

    return enriched
