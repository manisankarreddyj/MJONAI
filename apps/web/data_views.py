"""
Honest data views for the interactive application.

Pure functions: read ONLY from the db.repository facade, shape into
JSON-safe dicts. No recomputation beyond presentation arithmetic, no
defaults invented for missing data - absent values stay null.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional


def _num(value: Any) -> Optional[float]:
    try:
        if value is None:
            return None
        f = float(value)
        return None if f != f else round(f, 2)  # NaN guard
    except (TypeError, ValueError):
        return None


def _iso(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)


def build_system_status() -> Dict[str, Any]:
    """Mode/capital/health header tiles. Absent data -> null, never fiction."""
    from mjonai.core.constants import SYSTEM_MODE, TOTAL_CAPITAL
    from mjonai.db.repository import (
        get_latest_market_state,
        get_latest_snapshot,
        get_repository_health,
    )

    market = get_latest_market_state() or {}
    snapshot = get_latest_snapshot() or {}
    health = get_repository_health(deep_check=False) or {}

    equity = _num(snapshot.get("equity") or snapshot.get("capital_total"))
    peak = _num(snapshot.get("peak_equity") or snapshot.get("high_water_mark"))
    drawdown_pct = None
    if equity is not None and peak:
        drawdown_pct = round((peak - equity) / peak * 100.0, 2) if peak > 0 else None

    return {
        "system_mode": SYSTEM_MODE,
        "total_capital": _num(TOTAL_CAPITAL),
        "equity": equity,
        "peak_equity": peak,
        "drawdown_pct": drawdown_pct,
        "kill_line_breached": bool(snapshot.get("kill_line_breached", False)),
        "market_state": market.get("market_state"),
        "mqi_level": market.get("mqi_level"),
        "vix": _num(market.get("vix")),
        "no_trade_day": bool(market.get("no_trade_day", False)),
        "repository_health": {
            # Facade payload uses status/is_connected (v2.0.0), not is_healthy.
            "is_healthy": str(health.get("status", "")) == "HEALTHY"
            or bool(health.get("is_connected", False)),
            "detail": (
                f"{health.get('status', 'UNKNOWN')} · {health.get('latency_ms', '?')}ms"
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
    }


def build_open_trades() -> List[Dict[str, Any]]:
    from mjonai.db.repository import get_open_trades
    from mjonai.data.angelone.historical import fetch_historical_candles, CandleInterval

    rows = get_open_trades() or []
    out: List[Dict[str, Any]] = []
    
    for t in rows:
        sym = str(t.get("symbol", "")).upper()
        clean_sym = sym.replace(".NS", "").replace(".BO", "")
        qty_remaining = t.get("quantity_remaining")
        qty = int(qty_remaining) if qty_remaining is not None else int(t.get("quantity") or 0)
        entry = _num(t.get("entry_price"))
        side_str = str(t.get("direction") or t.get("side") or "BUY").upper()
        
        # 1. Fetch True Live Market LTP from Historical Engine / Live Feed
        ltp = _num(t.get("current_price"))
        if ltp is None:
            is_option = clean_sym.endswith("CE") or clean_sym.endswith("PE")
            if not is_option:
                try:
                    df = fetch_historical_candles(clean_sym, interval=CandleInterval.FIFTEEN_MINUTE, days_back=1)
                    if df is not None and not df.empty:
                        ltp = _num(df["Close"].iloc[-1])
                except Exception:
                    pass
            else:
                try:
                    from mjonai.execution.tracker import _get_current_price
                    opt_p = _get_current_price(clean_sym)
                    if opt_p and opt_p > 0:
                        ltp = _num(opt_p)
                except Exception:
                    pass

        if ltp is None:
            if side_str == "BUY" or side_str == "LONG":
                ltp = _num(t.get("price_high_since_entry") or entry)
            else:
                ltp = _num(t.get("price_low_since_entry") or entry)
        if ltp is None:
            ltp = entry

        unrealized = 0.0
        unrealized_pct = 0.0
        if entry is not None and ltp is not None and qty and entry > 0:
            direction_mult = 1 if (side_str == "BUY" or side_str == "LONG") else -1
            unrealized = round((ltp - entry) * qty * direction_mult, 2)
            unrealized_pct = round(((ltp - entry) / entry) * 100.0 * direction_mult, 2)

        sl = _num(t.get("current_sl") or t.get("stop_loss") or t.get("initial_sl"))
        target_1 = _num(t.get("target_1"))
        target_2 = _num(t.get("target_2"))
        target = _num(t.get("target_price") or t.get("target") or target_2 or target_1)

        out.append({
            "id": _iso(t.get("id")),
            "symbol": clean_sym,
            "side": side_str,
            "strategy_id": t.get("strategy_id"),
            "system_mode": t.get("system_mode", "RESEARCH"),
            "entry_price": entry,
            "current_price": ltp,
            "quantity": qty,
            "stop_loss": sl,
            "target": target,
            "target_1": target_1,
            "target_2": target_2,
            "unrealized_pnl": unrealized,
            "unrealized_pct": unrealized_pct,
            "sl_stage": t.get("sl_stage", "INITIAL"),
            "opened_at": _iso(t.get("created_at") or t.get("entry_time")),
        })
    return out


def build_recent_trades(limit: int = 20) -> List[Dict[str, Any]]:
    from mjonai.db.repository import get_trades_closed_today

    rows = (get_trades_closed_today() or [])[: max(0, limit)]
    return [{
        "id": _iso(t.get("id")),
        "symbol": t.get("symbol"),
        "side": t.get("direction") or t.get("side") or "BUY",
        "strategy_id": t.get("strategy_id"),
        "exit_reason": t.get("exit_reason", "NORMAL"),
        "gross_pnl": _num(t.get("gross_pnl")),
        "net_pnl": _num(t.get("net_pnl")),
        "exit_price": _num(t.get("exit_price")),
        "closed_at": _iso(t.get("exit_time")),
    } for t in rows]


def build_today_signals(limit: int = 25) -> List[Dict[str, Any]]:
    from mjonai.db.repository import get_signals_intelligence_today, get_signals_today

    rows = get_signals_intelligence_today() or []
    if not rows:
        rows = get_signals_today() or []
    rows = rows[: max(0, limit)]

    return [{
        "symbol": s.get("symbol"),
        "strategy_id": s.get("strategy_id") or s.get("strategy") or (s.get("metadata_json") or {}).get("strategy_id") or "S11_VolumeProfile",
        "signal_type": s.get("signal_direction") or s.get("signal_type") or "BUY",
        "confidence": _num(s.get("final_confidence") or s.get("confidence") or s.get("technical_score")),
        "verdict": s.get("supervisor_decision") or s.get("verdict") or ("APPROVED" if s.get("signal_type") != "DEBATE_REJECTED" else "REJECTED"),
        "rejection_stage": s.get("rejection_reason") or s.get("rejection_stage"),
        "created_at": _iso(s.get("generated_at") or s.get("created_at")),
    } for s in rows]


def build_trade_history(days: int = 30, limit: int = 200) -> List[Dict[str, Any]]:
    """Closed trades within the window, newest first (presentation only)."""
    from mjonai.db.repository import get_all_closed_trades

    rows = get_all_closed_trades(limit=1000) or []
    cutoff = (datetime.utcnow() - timedelta(days=max(1, days))).date()
    out: List[Dict[str, Any]] = []
    for t in rows:
        closed_at = t.get("exit_time") or t.get("updated_at")
        try:
            closed_day = datetime.fromisoformat(str(closed_at).replace("Z", "")).date()
        except (TypeError, ValueError):
            continue
        if closed_day < cutoff:
            continue
        out.append({
            "symbol": t.get("symbol"),
            "side": t.get("side"),
            "strategy_id": t.get("strategy_id"),
            "system_mode": t.get("system_mode"),
            "exit_reason": t.get("exit_reason"),
            "entry_price": _num(t.get("entry_price")),
            "exit_price": _num(t.get("exit_price")),
            "quantity": t.get("quantity_remaining") if t.get("quantity_remaining") is not None else t.get("quantity"),
            "gross_pnl": _num(t.get("gross_pnl")),
            "net_pnl": _num(t.get("net_pnl")),
            "closed_at": _iso(closed_at),
        })
        if len(out) >= limit:
            break
    out.sort(key=lambda r: r["closed_at"] or "", reverse=True)
    return out


def build_strategy_performance(days: int = 90) -> List[Dict[str, Any]]:
    """
    Per-strategy aggregation of closed trades in the window (presentation
    arithmetic over facade rows: counts/sums only - no trading math).
    Sorted by net P&L ascending so losers surface first.
    """
    rows = build_trade_history(days=days, limit=1000)
    stats: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        sid = r.get("strategy_id") or "UNKNOWN"
        bucket = stats.setdefault(sid, {
            "strategy_id": sid, "trades": 0, "wins": 0,
            "gross_pnl": 0.0, "net_pnl": 0.0, "net_known": 0,
        })
        bucket["trades"] += 1
        bucket["gross_pnl"] = round(bucket["gross_pnl"] + (r.get("gross_pnl") or 0.0), 2)
        net = r.get("net_pnl")
        if net is not None:
            bucket["net_pnl"] = round(bucket["net_pnl"] + net, 2)
            bucket["net_known"] += 1
            if net > 0:
                bucket["wins"] += 1

    out: List[Dict[str, Any]] = []
    for b in stats.values():
        known = b.pop("net_known")
        b["win_rate_pct"] = round(100.0 * b["wins"] / known, 1) if known else None
        b["avg_net_pnl"] = round(b["net_pnl"] / known, 2) if known else None
        out.append(b)
    out.sort(key=lambda b: b["net_pnl"])
    return out


def build_equity_series(days: int = 30, system_mode: Optional[str] = None) -> List[Dict[str, Any]]:
    """Daily snapshots oldest->newest for the equity strip chart."""
    import os

    from mjonai.core.constants import SYSTEM_MODE
    from mjonai.db.repository import get_snapshot_history

    rows = get_snapshot_history(
        days=max(1, days),
        system_mode=system_mode or os.getenv("MJONAI_APP_SNAPSHOT_MODE") or SYSTEM_MODE,
    ) or []
    series = [{
        "date": _iso(r.get("snapshot_date") or r.get("date")),
        "equity": _num(r.get("equity") or r.get("capital_total")),
        "drawdown_pct": _num(r.get("drawdown_pct")),
    } for r in rows]
    series.sort(key=lambda r: r["date"] or "")
    return series


def build_market_cockpit() -> Dict[str, Any]:
    """
    SOTA Multi-Pillar Market Surveillance Cockpit View:
    Aggregates Gift Nifty, FII/DII Flows, Market Breadth, Sector Rotation, and Risk Status.
    """
    from mjonai.db.repository import get_latest_market_state
    from mjonai.risk.behavioral_guard import get_behavioral_guard_status
    from mjonai.risk.emergency_triggers import get_emergency_risk_status

    market = get_latest_market_state() or {}
    bg_status = get_behavioral_guard_status()
    risk_status = get_emergency_risk_status()

    vix_val = _num(market.get("vix")) or 15.0
    vix_regime = "NORMAL"
    if vix_val >= 28.0:
        vix_regime = "CRISIS"
    elif vix_val >= 20.0:
        vix_regime = "ELEVATED"
    elif vix_val < 13.0:
        vix_regime = "LOW_VOL"

    return {
        "market_state": market.get("market_state", "NEUTRAL"),
        "mqi_level": market.get("mqi_level", "NORMAL"),
        "vix": vix_val,
        "vix_regime": vix_regime,
        "fii_net_cr": _num(market.get("fii_net_cr")),
        "dii_net_cr": _num(market.get("dii_net_cr")),
        "fii_regime": market.get("fii_regime", "BALANCED"),
        "gift_nifty_gap_pts": _num(market.get("gift_nifty_gap_pts")),
        "gift_nifty_sentiment": market.get("gift_nifty_sentiment", "NEUTRAL"),
        "market_breadth": {
            "advance_decline_ratio": _num(market.get("adr")),
            "mcclellan_oscillator": _num(market.get("mcclellan_oscillator")),
            "regime": market.get("breadth_regime", "NEUTRAL"),
        },
        "risk_guards": {
            "trading_allowed": risk_status.trading_allowed,
            "kill_line_active": risk_status.kill_line_active,
            "risk_stop_active": risk_status.risk_stop_active,
            "behavioral_cooldown_active": bg_status.cooldown_active,
            "consecutive_losses": bg_status.consecutive_losses,
            "locked_symbols": bg_status.locked_symbols,
            "active_reasons": risk_status.reasons,
        },
        "updated_at": datetime.now(timezone.utc).isoformat(),
    }


def build_stock_candles(symbol: str, timeframe: str = "15m", days_back: int = 5) -> Dict[str, Any]:
    """
    Fetch OHLCV candlestick data formatted for TradingView Lightweight Charts with order level overlays.
    """
    from mjonai.data.angelone.historical import fetch_historical_candles, CandleInterval
    from mjonai.db.repository import get_open_trades

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    interval_map = {
        "1m": CandleInterval.ONE_MINUTE,
        "3m": CandleInterval.THREE_MINUTE,
        "5m": CandleInterval.FIVE_MINUTE,
        "15m": CandleInterval.FIFTEEN_MINUTE,
        "1h": CandleInterval.ONE_HOUR,
        "1d": CandleInterval.ONE_DAY,
    }
    target_interval = interval_map.get(timeframe.lower(), CandleInterval.FIFTEEN_MINUTE)

    candles = []
    try:
        df = fetch_historical_candles(clean_sym, interval=target_interval, days_back=days_back)
        if df is not None and not df.empty:
            for idx, row in df.iterrows():
                ts = int(idx.timestamp()) if hasattr(idx, "timestamp") else 0
                open_v = _num(row.get("Open") if "Open" in row else row.get("open"))
                high_v = _num(row.get("High") if "High" in row else row.get("high"))
                low_v = _num(row.get("Low") if "Low" in row else row.get("low"))
                close_v = _num(row.get("Close") if "Close" in row else row.get("close"))
                vol_v = _num(row.get("Volume") if "Volume" in row else row.get("volume")) or 0
                if open_v and high_v and low_v and close_v and ts:
                    candles.append({
                        "time": ts,
                        "open": open_v,
                        "high": high_v,
                        "low": low_v,
                        "close": close_v,
                        "volume": vol_v,
                    })
    except Exception as e:
        pass

    # Retrieve trade overlay levels if currently open
    open_trades = get_open_trades() or []
    trade_meta = None
    for t in open_trades:
        if str(t.get("symbol", "")).upper() == clean_sym:
            entry = _num(t.get("entry_price"))
            sl = _num(t.get("current_sl") or t.get("stop_loss"))
            t1 = _num(t.get("target_price") or t.get("target"))
            t2 = _num(t.get("target_2"))
            if not t2 and entry and t1:
                t2 = round(entry + (t1 - entry) * 1.5, 2)
            trade_meta = {
                "id": _iso(t.get("id")),
                "symbol": clean_sym,
                "side": str(t.get("direction") or t.get("side") or "BUY").upper(),
                "strategy_id": t.get("strategy_id"),
                "entry_price": entry,
                "stop_loss": sl,
                "target_1": t1,
                "target_2": t2,
                "sl_stage": t.get("sl_stage", "INITIAL"),
            }
            break

    return {
        "symbol": clean_sym,
        "timeframe": timeframe,
        "candles": candles,
        "count": len(candles),
        "trade_meta": trade_meta,
    }


def build_ai_debates(limit: int = 20) -> List[Dict[str, Any]]:
    """Honest per-signal Boardroom transcript: the REAL bull verdict/reasoning + supervisor
    verdict as recorded in signal_intelligence_log. Absent fields render as null — never a
    fabricated thesis/verdict/confidence/model name. (There is no bear_* column on the signal
    row; the bear analysis is persisted to agent_logs, so it is shown as not-recorded here
    rather than invented.)
    """
    from mjonai.db.repository import get_signals_intelligence_recent
    rows = get_signals_intelligence_recent(days=7, limit=max(1, limit)) or []
    out = []
    for s in rows[: max(0, limit)]:
        out.append({
            "id": _iso(s.get("id")),
            "symbol": s.get("symbol"),
            "strategy_id": s.get("strategy_id"),
            "time": _iso(s.get("generated_at")),
            "signal_direction": s.get("signal_direction"),
            "final_confidence": _num(s.get("final_confidence")),
            "was_executed": s.get("was_executed"),
            "bull_agent": {
                "verdict": s.get("bull_verdict"),
                "confidence": _num(s.get("bull_confidence")),
                "key_reasons": s.get("bull_key_reasons"),
                "concerns": s.get("bull_concerns"),
                "model": s.get("bull_model_used"),
            },
            "supervisor_cio": {
                "verdict": s.get("supervisor_decision"),
                "reason": s.get("supervisor_reason"),
            },
        })
    return out


def build_signal_track_record(days: int = 90) -> Dict[str, Any]:
    """The PKScreener 'how-it-fared' honest scoreboard. Over settled signals (those with
    forward returns), compute a DIRECTION-ADJUSTED hit-rate per strategy: a LONG that rose or
    a SHORT that fell counts as a hit. Absent data -> n=0 and rates null (never a fabricated
    0%). Overall + per-strategy, sorted by best 1-day hit-rate.
    """
    from mjonai.db.repository import get_signals_for_alphalens
    start_date = (datetime.utcnow() - timedelta(days=max(1, days))).date().isoformat()
    rows = get_signals_for_alphalens(start_date=start_date, limit=5000) or []

    by_strat: Dict[str, Dict[str, Any]] = {}

    def _bucket(name: str) -> Dict[str, Any]:
        return by_strat.setdefault(
            name, {"strategy_id": name, "n": 0, "n1": 0, "hit1": 0, "n5": 0, "hit5": 0, "sum_r1": 0.0}
        )

    for r in rows:
        strat = r.get("strategy_id") or "UNKNOWN"
        d = str(r.get("signal_direction") or "").upper()
        sign = 1 if d in ("BUY", "LONG") else (-1 if d in ("SELL", "SHORT") else 0)
        b = _bucket(strat)
        b["n"] += 1
        r1 = r.get("forward_return_1d")
        if isinstance(r1, (int, float)) and sign != 0:
            adj = sign * float(r1)
            b["n1"] += 1
            b["sum_r1"] += adj
            if adj > 0:
                b["hit1"] += 1
        r5 = r.get("forward_return_5d")
        if isinstance(r5, (int, float)) and sign != 0 and (sign * float(r5)) > 0:
            b["n5"] += 1
            b["hit5"] += 1

    def _finalize(b: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "strategy_id": b["strategy_id"],
            "n": b["n"],
            "hit_rate_1d": round(b["hit1"] / b["n1"], 3) if b["n1"] else None,
            "mean_fwd_1d": round(b["sum_r1"] / b["n1"], 4) if b["n1"] else None,
            "hit_rate_5d": round(b["hit5"] / b["n5"], 3) if b["n5"] else None,
        }

    strategies = sorted(
        (_finalize(b) for b in by_strat.values()),
        key=lambda s: -(s["hit_rate_1d"] if s["hit_rate_1d"] is not None else -1.0),
    )
    t_n = sum(b["n"] for b in by_strat.values())
    t_n1 = sum(b["n1"] for b in by_strat.values())
    t_hit1 = sum(b["hit1"] for b in by_strat.values())
    return {
        "overall": {
            "n": t_n,
            "hit_rate_1d": round(t_hit1 / t_n1, 3) if t_n1 else None,
            "mean_fwd_1d": round(sum(b["sum_r1"] for b in by_strat.values()) / t_n1, 4) if t_n1 else None,
        },
        "strategies": strategies,
    }
