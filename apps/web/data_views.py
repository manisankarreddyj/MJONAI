"""
Honest data views for the interactive application.

Pure functions: read ONLY from the db.repository facade, shape into
JSON-safe dicts. No recomputation beyond presentation arithmetic, no
defaults invented for missing data - absent values stay null.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional



# NSE Sector Mapping (clean-room, based on standard NSE industry classification)
# Covers the 497-symbol equity panel. Symbols not in this map fall under "OTHERS".
NSE_SECTOR_MAP: Dict[str, str] = {
    # BANKS & FINANCIAL
    "HDFCBANK": "BANKS", "ICICIBANK": "BANKS", "SBIN": "BANKS", "KOTAKBANK": "BANKS",
    "AXISBANK": "BANKS", "INDUSINDBK": "BANKS", "FEDERALBNK": "BANKS", "BANKBARODA": "BANKS",
    "PNB": "BANKS", "CANBK": "BANKS", "UNIONBANK": "BANKS", "IDFCFIRSTB": "BANKS",
    "RBLBANK": "BANKS", "YESBANK": "BANKS", "BANDHANBNK": "BANKS",
    # NBFC & INSURANCE
    "BAJFINANCE": "NBFC", "BAJAJFINSV": "NBFC", "SHRIRAMFIN": "NBFC", "CHOLAFIN": "NBFC",
    "MUTHOOTFIN": "NBFC", "M&MFIN": "BANKS", "LICHSGFIN": "NBFC", "PFC": "NBFC",
    "RECLTD": "NBFC", "ICICIPRULI": "INSURANCE", "HDFCLIFE": "INSURANCE", "SBILIFE": "INSURANCE",
    "ICICIGI": "INSURANCE", "NICOLG": "INSURANCE", "NEWINDIA": "INSURANCE",
    # IT & TECH
    "TCS": "IT", "INFY": "IT", "HCLTECH": "IT", "WIPRO": "IT", "TECHM": "IT",
    "LTIM": "IT", "MPHASIS": "IT", "PERSISTENT": "IT", "COFORGE": "IT",
    "LTTS": "IT", "CYIENT": "IT", "KPITTECH": "IT", "TATAELXSI": "IT",
    "ZENSARTECH": "IT", "SONATSOFTW": "IT", "INTELLECT": "IT", "BSOFT": "IT",
    # AUTO & AUTO ANCILLARIES
    "MARUTI": "AUTO", "TATAMOTORS": "AUTO", "M&M": "AUTO", "BAJAJ-AUTO": "AUTO",
    "EICHERMOT": "AUTO", "HEROMOTOCO": "AUTO", "TVSMOTOR": "AUTO", "ASHOKLEY": "AUTO",
    "BHARATFORG": "AUTO", "MOTHERSON": "AUTO", "BOSCHLTD": "AUTO", "SUNDRMFAST": "AUTO",
    "SCHAEFFLER": "AUTO", "MRF": "AUTO", "APOLLOTYRE": "AUTO", "CEATLTD": "AUTO",
    # CONSUMER DURABLES & FMCG
    "HINDUNILVR": "FMCG", "ITC": "FMCG", "NESTLEIND": "FMCG", "BRITANNIA": "FMCG",
    "DABUR": "FMCG", "GODREJCP": "FMCG", "MARICO": "FMCG", "COLPAL": "FMCG",
    "EMAMILTD": "FMCG", "TATACONSUM": "FMCG", "UBL": "FMCG", "RADICO": "FMCG",
    "TITAN": "CONSUMER_DURABLES", "VOLTAS": "CONSUMER_DURABLES", "BLUESTARCO": "CONSUMER_DURABLES",
    "WHIRLPOOL": "CONSUMER_DURABLES", "HAVELLS": "CONSUMER_DURABLES", "CROMPTON": "CONSUMER_DURABLES",
    # PHARMA & HEALTHCARE
    "SUNPHARMA": "PHARMA", "CIPLA": "PHARMA", "DRREDDY": "PHARMA", "DIVISLAB": "PHARMA",
    "BIOCON": "PHARMA", "LUPIN": "PHARMA", "TORNTPHARM": "PHARMA", "ALKEM": "PHARMA",
    "AUROPHARMA": "PHARMA", "ZYDUSLIFE": "PHARMA", "GLENMARK": "PHARMA", "LAURUSLABS": "PHARMA",
    "ABBOTINDIA": "PHARMA", "PFIZER": "PHARMA", "SANOFI": "PHARMA",
    # OIL & GAS
    "RELIANCE": "OIL_GAS", "ONGC": "OIL_GAS", "IOC": "OIL_GAS", "BPCL": "OIL_GAS",
    "HPCL": "OIL_GAS", "GAIL": "OIL_GAS", "PETRONET": "OIL_GAS", "OIL": "OIL_GAS",
    "IGL": "OIL_GAS", "MGL": "OIL_GAS", "AEGISLOG": "OIL_GAS",
    # METALS & MINING
    "TATASTEEL": "METALS", "JSWSTEEL": "METALS", "JINDALSTEL": "METALS", "SAIL": "METALS",
    "HINDALCO": "METALS", "VEDL": "METALS", "NMDC": "METALS", "NTPC": "POWER",
    "POWERGRID": "POWER", "ADANIPOWER": "POWER", "TORNTPOWER": "POWER", "JSWENERGY": "POWER",
    "NHPC": "POWER", "SJVN": "POWER",
    # CEMENT & BUILDING MATERIALS
    "ULTRACEMCO": "CEMENT", "SHREECEM": "CEMENT", "GRASIM": "CEMENT", "AMBUJACEM": "CEMENT",
    "ACC": "CEMENT", "DALBHARAT": "CEMENT", "RAMCOCEM": "CEMENT", "JKCEMENT": "CEMENT",
    # CHEMICALS
    "PIDILITIND": "CHEMICALS", "ASIANPAINT": "CHEMICALS", "BERGERPAINT": "CHEMICALS",
    "KANSAINER": "CHEMICALS", "SRF": "CHEMICALS", "NAVINFLUOR": "CHEMICALS",
    "DEEPAKNTR": "CHEMICALS", "TATACHEM": "CHEMICALS", "GNFC": "CHEMICALS",
    # TELECOM
    "BHARTIARTL": "TELECOM", "IDEA": "TELECOM", "INDUSTOWER": "TELECOM",
    # INFRASTRUCTURE & CONSTRUCTION
    "LT": "INFRA", "ADANIENT": "INFRA", "ADANIPORTS": "INFRA", "ADANIGREEN": "INFRA",
    "ADANITRANS": "INFRA", "GMRINFRA": "INFRA", "IRB": "INFRA", "IRCTC": "INFRA",
    "RVNL": "INFRA", "NBCC": "INFRA", "KEC": "INFRA", "KALPATPOWR": "INFRA",
    # CAPITAL GOODS & ENGINEERING
    "BHEL": "CAPITAL_GOODS", "SIEMENS": "CAPITAL_GOODS", "ABB": "CAPITAL_GOODS",
    "CROMPTON": "CAPITAL_GOODS", "THERMAX": "CAPITAL_GOODS", "VOLTAS": "CAPITAL_GOODS",
    "BEL": "CAPITAL_GOODS", "HAL": "CAPITAL_GOODS", "CUMMINSIND": "CAPITAL_GOODS",
    # TEXTILES
    "TRENT": "TEXTILES", "PAGEIND": "TEXTILES", "RAYMOND": "TEXTILES", "VARDHACRLC": "TEXTILES",
    # REALTY
    "DLF": "REALTY", "GODREJPROP": "REALTY", "OBEROIRLTY": "REALTY", "PRESTIGE": "REALTY",
    "PHOENIXLTD": "REALTY", "BRIGADE": "REALTY", "SOBHA": "REALTY",
    # RETAIL
    "DMART": "RETAIL", "TRENT": "RETAIL", "ZOMATO": "RETAIL", "NYKAA": "RETAIL",
    # OTHERS
    "ADANIENT": "CONGLOMERATE", "ADANIGREEN": "CONGLOMERATE", "ADANIPORTS": "CONGLOMERATE",
    "ADANITRANS": "CONGLOMERATE", "ADANIPOWER": "CONGLOMERATE", "ADANIENSOL": "CONGLOMERATE",
}

def _get_sector(symbol: str) -> str:
    """Map a symbol to its NSE sector, defaulting to OTHERS.

    Precedence: hand-written NSE_SECTOR_MAP first (finer BANKS/NBFC/
    INSURANCE, RETAIL-name and conglomerate judgement calls), then the
    generated NSE-Industry overlay (`mjonai/data/nse_industry_overlay.py`,
    openalgo-heatmap row-39 mirror), then OTHERS. The overlay import is
    lazy and guarded: a missing/regenerating artifact degrades to
    hand-map-only coverage, never to an exception.
    """
    clean = symbol.upper().replace(".NS", "").replace(".BO", "")
    if clean in NSE_SECTOR_MAP:
        return NSE_SECTOR_MAP[clean]
    try:
        from mjonai.data.nse_industry_overlay import NSE_INDUSTRY_OVERLAY
    except Exception:
        return "OTHERS"
    return NSE_INDUSTRY_OVERLAY.get(clean, "OTHERS")

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
                f"{health.get('status', 'UNKNOWN')} ┬╖ {health.get('latency_ms', '?')}ms"
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds") + "Z",
    }


def build_open_trades() -> List[Dict[str, Any]]:
    from mjonai.db.repository import get_open_trades
    from mjonai.data.angelone.historical import fetch_historical_candles, CandleInterval

    from mjonai.core.constants import SYSTEM_MODE
    rows = get_open_trades(system_mode=SYSTEM_MODE) or []
    out: List[Dict[str, Any]] = []
    
    for t in rows:
        sym = str(t.get("symbol", "")).upper()
        clean_sym = sym.replace(".NS", "").replace(".BO", "")
        qty_remaining = t.get("quantity_remaining")
        qty = int(qty_remaining) if qty_remaining is not None else int(t.get("quantity") or 0)
        entry = _num(t.get("entry_price"))
        side_str = str(t.get("direction") or t.get("side") or "BUY").upper()
        
        # 1. True live LTP from the feed, else a LABELLED delayed fallback,
        # else honest nulls. P0 fix: the old chain fell back to
        # price_high/low_since_entry and finally entry itself, then booked
        # unrealized P&L off that fiction (a dead feed read as flat). A
        # missing price is now null + stale:true — never entry-as-LTP.
        ltp = _num(t.get("current_price"))
        price_source = "live" if ltp is not None else None
        if ltp is None:
            is_option = clean_sym.endswith("CE") or clean_sym.endswith("PE")
            if not is_option:
                try:
                    df = fetch_historical_candles(clean_sym, interval=CandleInterval.FIFTEEN_MINUTE, days_back=1)
                    if df is not None and not df.empty:
                        ltp = _num(df["Close"].iloc[-1])
                        price_source = "delayed_15m" if ltp is not None else None
                except Exception:
                    pass
            else:
                try:
                    from mjonai.execution.tracker import _get_current_price
                    opt_p = _get_current_price(clean_sym)
                    if opt_p and opt_p > 0:
                        ltp = _num(opt_p)
                        price_source = "live" if ltp is not None else None
                except Exception:
                    pass

        unrealized = None
        unrealized_pct = None
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
            "price_source": price_source,
            "stale": ltp is None,
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
    from mjonai.core.constants import SYSTEM_MODE
    open_trades = get_open_trades(system_mode=SYSTEM_MODE) or []
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
    verdict as recorded in signal_intelligence_log. Absent fields render as null ΓÇö never a
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


# ΓöÇΓöÇ ADR-0012 research preview: Kronos forecast band ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# The verdict must travel with every payload ΓÇö a failed model may be shown for
# research telemetry, never silently as a "signal".
_KRONOS_VERDICT = (
    "RESEARCH PREVIEW ΓÇö Kronos-mini FAILED the ADR-0002 adoption bar (RELIANCE daily, 60 origins, "
    "2026-10-11: worst MAE 31.64, 42.0% dir-acc, 0.0% q10ΓÇôq90 coverage, net ΓêÆ25.31% vs "
    "seasonal_naive ΓêÆ5.63%). Not a signal ΓÇö research telemetry only."
)
_FORECAST_CACHE: Dict[Any, Dict[str, Any]] = {}
_FORECAST_CACHE_TTL_S = 3600
_FORECAST_CACHE_LOCK = threading.Lock()


# ΓöÇΓöÇ ADR-0013 research preview: SMC structure markers (snapshot channel) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# apps/web may NOT import mjonai.research.discovery (machine-enforced fence), so
# the research-tier CLI (apps/research/run_smc_structure_export.py) computes the
# leakage-safe markers and this view reads the persisted snapshot. Absent snapshot
# => available=false with the fetch command; markers are never fabricated.
_SMC_SNAPSHOT_DIR = Path(__file__).resolve().parents[2] / "storage" / "research" / "smc_structure"
_SMC_DISCLOSURE = (
    "RESEARCH PREVIEW ΓÇö SMC structure (vendored joshyattridge/smart-money-concepts, MIT), leakage-safe: "
    "swings confirmed with a swing_length+2 bar lag, FVGs one bar late. Research verdict (NIFTY spot "
    "2014-2026, net): RISK OVERLAY, NOT ALPHA (MaxDD 38.4%->22.9%, WRC p=0.878, CAGR 8.4% < B&H 11.4%) "
    "ΓÇö annotations only; not a signal."
)
_SMC_EXPORT_HINT = "run apps/research/run_smc_structure_export.py --symbol {symbol} --tf {tf}"


# ΓöÇΓöÇ Options desk (OpenAlgo reference cluster, registry #8) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# Descriptive analytics over the official F&O EOD chain warehouse already on disk.
# Research-tier DISPLAY only ΓÇö no signal, no edge claim; the warehouse is a single
# source and every miss fails closed with a reason.
_OPTIONS_DISCLOSURE = (
    "RESEARCH DATA VIEW ΓÇö analytics over the official F&O EOD chain warehouse "
    "(NSE bhavcopy + TradingTick, nearest-money expiry). Descriptive only: not a signal, "
    "no edge claim, and it cannot place orders."
)


def build_option_chain(symbol: str, as_of: str, strikes: int = 7) -> Dict[str, Any]:
    """Full options-desk payload for one underlying/date: chain + window PCR + max
    pain + OI profile/track + IV smile + vol surface + GEX + per-strike Greeks.

    Fail-closed: a missing warehouse month, a non-F&O underlying, or a non-trading
    date returns {"available": False, "reason": ...} ΓÇö never an empty chain presented
    as a zero-OI reading.
    """
    import pandas as pd

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")

    def _miss(reason: str) -> Dict[str, Any]:
        return {"available": False, "symbol": clean_sym, "as_of": as_of,
                "reason": reason, "disclosure": _OPTIONS_DISCLOSURE}

    try:
        from mjonai.research.data.fno_eod import load_eod_chain_for_date
        from mjonai.research.data.option_desk import chain_window, max_pain, oi_profile, window_pcr
        from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR
    except Exception as exc:  # kernel wiring problem is an honest miss too
        return _miss(f"options analytics unavailable: {exc}")
    try:
        ts = pd.Timestamp(as_of).normalize()
        frame = load_eod_chain_for_date(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts)
    except Exception as exc:
        return _miss(f"chain read failed: {exc}")
    if frame is None:
        return _miss(f"no chain rows for {clean_sym} on {ts.date().isoformat()} "
                     "(run apps/research/run_fno_backfill.py to extend the warehouse)")

    try:
        win = chain_window(frame, n_strikes=max(1, min(int(strikes), 25)))
        if not win["rows"]:
            return _miss("chain window empty for this date")
        from mjonai.research.data.option_desk import (
            gex_profile, greeks_for_strikes, greeks_history, iv_smile, oi_history, oi_track, straddle_series, vol_surface,
        )
        dte_days = max(0, (pd.Timestamp(min(pd.to_datetime(frame["expiry"]))).normalize() - ts).days)
        smile = iv_smile(win["rows"], win["spot"], dte_days)
        gex = gex_profile(frame, win["rows"], smile, win["spot"], dte_days)
        greeks = greeks_for_strikes(win["rows"], smile, win["spot"], dte_days)
        oi_changes = oi_track(win["rows"])
        try:
            surface = vol_surface(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts, max_expiries=4)
        except Exception as exc:
            surface = {"error": str(exc)}
        try:
            history = oi_history(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts,
                                 min(pd.to_datetime(frame["expiry"])),
                                 n_strikes=max(1, min(int(strikes), 25)), lookback_days=12)
        except Exception as exc:
            history = {"error": str(exc)}
        try:
            gh = greeks_history(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts,
                                min(pd.to_datetime(frame["expiry"])),
                                lookback_days=12)
        except Exception as exc:
            gh = {"error": str(exc)}
        try:
            st = straddle_series(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts,
                                 min(pd.to_datetime(frame["expiry"])),
                                 lookback_days=12)
        except Exception as exc:
            st = {"error": str(exc)}
        payload = {
            "available": True,
            "symbol": clean_sym,
            "as_of": ts.date().isoformat(),
            "expiries": sorted({str(pd.Timestamp(e).date()) for e in frame["expiry"]}),
            "spot": win["spot"],
            "dte_days": dte_days,
            "window_pcr": window_pcr(win["rows"]),
            "max_pain": max_pain(frame),
            "oi_profile": oi_profile(win["rows"]),
            "oi_track": oi_changes,
            "iv_smile": smile,
            "gex": gex,
            "greeks": greeks,
            "vol_surface": surface,
            "oi_history": history,
            "greeks_history": gh,
            "straddle_series": st,
            "rows": win["rows"],
            "disclosure": _OPTIONS_DISCLOSURE,
        }
        return payload
    except Exception as exc:
        return _miss(f"chain analytics failed: {exc}")


# ΓöÇΓöÇ Approval-gated decision console (OpenAlgo reference cluster #4) ΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇΓöÇ
# ADVISORY ONLY ΓÇö the app cannot place orders (ADR-0007). This console triages the
# pipeline's own recorded decisions for the operator's manual execution, and records
# the operator's disposition to the system_log telemetry journal. It never sizes,
# routes, or sends anything to a broker.
_APPROVE_VERDICTS = {"APPROVED", "APPROVE", "ACCEPT", "BUY", "STRONG_BUY", "EXECUTE"}
_CONSOLE_DISCLOSURE = (
    "ADVISORY CONSOLE ΓÇö triages the engine's recorded decisions for MANUAL execution. "
    "It records your disposition to the telemetry journal and cannot place orders (ADR-0007)."
)


def build_console_queue(limit: int = 12) -> Dict[str, Any]:
    """Signals the supervisor approved but the engine has not executed ΓÇö the manual
    execution queue ΓÇö each with its recorded evidence chain (bull verdict/reasons,
    supervisor reason, confidence). Absent data -> empty queue, never filler."""
    from mjonai.db.repository import get_signals_intelligence_recent

    rows = get_signals_intelligence_recent(days=2, limit=200) or []
    pending = []
    for s in rows:
        verdict = str(s.get("supervisor_decision") or "").upper()
        if verdict not in _APPROVE_VERDICTS or s.get("was_executed") is True:
            continue
        pending.append({
            "id": _iso(s.get("id")),
            "symbol": s.get("symbol"),
            "strategy_id": s.get("strategy_id"),
            "time": _iso(s.get("generated_at")),
            "signal_direction": s.get("signal_direction"),
            "final_confidence": _num(s.get("final_confidence")),
            "supervisor_reason": s.get("supervisor_reason"),
            "bull_verdict": s.get("bull_verdict"),
            "bull_confidence": _num(s.get("bull_confidence")),
            "bull_key_reasons": s.get("bull_key_reasons"),
            "bull_model_used": s.get("bull_model_used"),
        })
        if len(pending) >= max(0, limit):
            break
    return {"queue": pending, "count": len(pending), "disclosure": _CONSOLE_DISCLOSURE}


def record_console_decision(signal_id: str, action: str, note: str = "") -> Dict[str, Any]:
    """Journal an operator disposition (APPROVED_FOR_MANUAL / REJECTED / SNOOZED).

    Telemetry only: the disposition lands in system_log so the decision is auditable
    and replayable; nothing is sent to a broker and nothing is sized."""
    from mjonai.db.repository import insert_system_log

    action = str(action or "").upper()
    if action not in ("APPROVED_FOR_MANUAL", "REJECTED", "SNOOZED"):
        return {"recorded": False, "reason": f"unknown action '{action}'"}
    payload = {
        "signal_id": str(signal_id or ""),
        "action": action,
        "note": str(note or "")[:500],
        "at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        ok = bool(insert_system_log(
            event_type="OPERATOR_DECISION",
            message=f"{payload['action']} {payload['signal_id']} ΓÇö {payload['note']}".strip(" ΓÇö"),
            level="INFO",
        ))
    except Exception as exc:
        return {"recorded": False, "reason": f"journal write failed: {exc}"}
    return {"recorded": ok, "signal_id": payload["signal_id"], "action": payload["action"],
            "reason": None if ok else "journal writer returned false"}


# ΓöÇΓöÇ Finviz-pattern market overview (breadth strip + signal tables + heatmap) ΓöÇΓöÇΓöÇΓöÇ
def build_market_overview(top: int = 8) -> Dict[str, Any]:
    """Breadth + signal tables + heatmap rows over the local equity panel.

    Fail-closed: a missing/empty panel returns available=False with the reason
    (no fabricated breadth, no zero-filled universe).
    """
    out: Dict[str, Any] = {"available": False, "disclosure": ""}
    try:
        from mjonai.research.data.market_overview import market_overview
        data = market_overview(top=top)
    except Exception as exc:
        out["reason"] = f"market overview unavailable: {exc}"
        return out
    if not data:
        out["reason"] = "equity panel empty or absent (storage/parquet/yahoo_equity)"
        return out
    return data


# ΓöÇΓöÇ Bloomberg-pattern surfaces: research index (BQuant analog) + TCA (BTCA) ΓöÇΓöÇΓöÇΓöÇ
def build_research_index(limit: int = 40) -> Dict[str, Any]:
    """The research-management view: persisted verdict artifacts, newest first.

    Reads artifact headlines only (no strategy verdicts are recomputed); an
    unreadable artifact is listed as unreadable, never skipped silently.
    """
    out: Dict[str, Any] = {"available": False, "artifacts": []}
    try:
        from mjonai.research.evidence import (
            list_evidence,
            summarize_evidence,
            trial_summary,
        )

        paths = list_evidence(limit=limit)
        out["artifacts"] = [summarize_evidence(p) for p in paths]
        out["trial_summary"] = trial_summary(paths=paths)
        out["available"] = bool(paths)
        out["reason"] = (
            None
            if paths
            else "no verdict artifacts recorded yet ΓÇö run a walk-forward, discovery sweep, or forecast benchmark"
        )
    except Exception as exc:
        out["reason"] = f"evidence index unavailable: {exc}"
    return out


# ─── DBnomics Macro (keyless free-macro provider) ──────
def build_dbnomics_series(provider: str = "", dataset: str = "", series: str = "") -> Dict[str, Any]:
    """
    Fetch one macro series from the keyless DBnomics API.
    Fail-closed: blank codes or any fetch/parse failure returns
    available=False. Not a signal, descriptive analytics only.
    """
    try:
        from mjonai.data.dbnomics import DbnomicsProvider
    except Exception:
        return {"available": False, "reason": "DBnomics module not available"}

    out = DbnomicsProvider().fetch_series(provider, dataset, series)
    if out.get("available"):
        out["disclosure"] = (
            "RESEARCH DATA VIEW — macro observation from DBnomics (keyless public API). "
            "Fail-closed: blank codes or fetch failure return available=False. "
            "Not a signal, no edge claim."
        )
    return out


# ─── Run-compare (Vibe-Trading Compare.tsx, clean-room slice) ────────────────
_COMPARE_MAX_COLUMNS = 4
_COMPARE_SKIP_KEYS = frozenset({
    "symbols", "per_symbol_verdicts", "symbols_evaluated", "windows_total",
    "universe_size", "summary_rows", "rows",
})


def _compare_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Flatten one artifact payload to comparable scalar metric rows.

    Top-level scalars pass through (except index/plumbing keys); the two
    known nested verdict blocks (overall_verdict, statistical_validation)
    flatten one level with a prefix. Lists and deeper dicts are skipped —
    per-symbol tables stay in the artifact, never half-rendered here.
    """
    metrics: Dict[str, Any] = {}
    for key, value in payload.items():
        if key in _COMPARE_SKIP_KEYS:
            continue
        if isinstance(value, bool):
            metrics[key] = value
        elif isinstance(value, (int, float, str)):
            metrics[key] = value
        elif isinstance(value, dict) and key in ("overall_verdict", "statistical_validation"):
            for sub_key, sub_value in value.items():
                if isinstance(sub_value, bool) or isinstance(sub_value, (int, float, str)):
                    metrics[f"{key}.{sub_key}"] = sub_value
    return metrics


def build_evidence_compare(files) -> Dict[str, Any]:
    """Side-by-side metric columns over named verdict artifacts (read-only).

    `files` are artifact BASENAMES (e.g. "walk_forward_20261011_....json").
    Anything containing a path separator or parent reference is rejected —
    the evidence directory is never escapable via this endpoint. Per-file
    fail-closed: an unreadable artifact renders as an error column, never
    breaks the comparison. Capped at _COMPARE_MAX_COLUMNS columns.
    """
    from mjonai.research import evidence as evidence_mod

    out: Dict[str, Any] = {"available": False, "columns": []}
    names = [str(f or "").strip() for f in (files or [])]
    names = [n for n in names if n][: _COMPARE_MAX_COLUMNS]
    if not names:
        out["reason"] = "no artifact files selected — pass ?files=<basename> (up to 4)"
        return out
    target = evidence_mod.DEFAULT_EVIDENCE_DIR
    for name in names:
        if not name or "/" in name or "\\" in name or ".." in name:
            out["columns"].append({"file": name or "?", "error": "rejected: basename only, no paths"})
            continue
        try:
            data = json.loads((target / name).read_text(encoding="utf-8"))
        except Exception as exc:
            out["columns"].append({"file": name, "error": f"unreadable: {exc}"})
            continue
        payload = data.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        out["columns"].append({
            "file": name,
            "kind": data.get("kind"),
            "generated_at_utc": data.get("generated_at_utc"),
            "git_revision_short": data.get("git_revision_short"),
            "verdict": payload.get("verdict"),
            "metrics": _compare_metrics(payload),
        })
    out["available"] = any("error" not in c for c in out["columns"])
    if not out["available"]:
        out["reason"] = "no selected artifact was readable"
    # Field-level semantic diff when exactly two artifacts are comparable.
    readable = [c for c in out["columns"] if "error" not in c]
    if len(readable) == 2:
        try:
            from mjonai.research.evidence import diff_payloads
            pay_a = json.loads((target / readable[0]["file"]).read_text(encoding="utf-8")).get("payload") or {}
            pay_b = json.loads((target / readable[1]["file"]).read_text(encoding="utf-8")).get("payload") or {}
            out["diff"] = diff_payloads(pay_a if isinstance(pay_a, dict) else {},
                                        pay_b if isinstance(pay_b, dict) else {})
        except Exception as exc:
            out["diff"] = {"error": f"diff unavailable: {exc}"}
    out["disclosure"] = (
        "RESEARCH DATA VIEW — recorded verdict metrics side by side; nothing is "
        "recomputed. Absent fields render null, never zero. Not a signal."
    )
    return out


def build_tca(limit: int = 200) -> Dict[str, Any]:
    """Transaction cost analysis from the repository's own closed trades."""
    out: Dict[str, Any] = {"available": False}
    try:
        from mjonai.db.repository import get_all_closed_trades
        from mjonai.research.analytics.tca import build_tca as _tca
        trades = get_all_closed_trades(limit=limit) or []
        out.update(_tca(trades))
        if not out.get("available"):
            out.setdefault("reason", "no closed trades in scope")
    except Exception as exc:
        out.update({"available": False, "reason": f"TCA unavailable: {exc}"})
    return out


def build_option_payoff(
    legs: Optional[List[Dict[str, Any]]] = None,
    straddle: Optional[Dict[str, Any]] = None,
    points: int = 41,
    span_pct: float = 0.10,
    lot_size: int = 25,
) -> Dict[str, Any]:
    """Expiry payoff for option legs ΓÇö PURE math, no market data (the OpenAlgo
    strategy-builder/payoff-diagram pattern). Either pass explicit `legs` or a
    `straddle` spec {spot, ce_strike, pe_strike, ce_premium, pe_premium, side}.
    """
    from mjonai.research.data.option_desk import payoff_curve, straddle_pnl

    def _miss(reason: str) -> Dict[str, Any]:
        return {"available": False, "reason": reason, "disclosure": _OPTIONS_DISCLOSURE}

    try:
        if straddle:
            out = straddle_pnl(
                spot_price=float(straddle["spot"]),
                ce_strike=float(straddle["ce_strike"]), pe_strike=float(straddle["pe_strike"]),
                ce_premium=float(straddle["ce_premium"]), pe_premium=float(straddle["pe_premium"]),
                lot_size=int(lot_size), side=str(straddle.get("side", "BUY")),
                span_pct=span_pct, points=points,
            )
        elif legs:
            anchors = [float(l["strike"]) for l in legs if l.get("strike")]
            center = (min(anchors) + max(anchors)) / 2 if anchors else 0.0
            lo, hi = center * (1 - span_pct), center * (1 + span_pct)
            grid = [lo + (hi - lo) * i / max(1, points - 1) for i in range(points)]
            out = payoff_curve(legs, grid, lot_size=int(lot_size))
        else:
            return _miss("no legs or straddle spec supplied")
    except Exception as exc:
        return _miss(f"payoff math failed: {exc}")
    if not out["spots"]:
        return _miss("empty payoff grid")
    return {"available": True, **out, "disclosure": _OPTIONS_DISCLOSURE}


def build_smc_structure(symbol: str, timeframe: str = "1d") -> Dict[str, Any]:
    """Read the research-tier SMC structure snapshot for {symbol}_{timeframe}.json.
    Fail-closed: a missing/unreadable snapshot returns available=false + reason.
    """
    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    tf = (timeframe or "1d").lower()
    path = _SMC_SNAPSHOT_DIR / f"{clean_sym}_{tf}.json"

    def _miss(reason: str) -> Dict[str, Any]:
        return {"available": False, "symbol": clean_sym, "timeframe": tf, "reason": reason,
                "disclosure": _SMC_DISCLOSURE}

    if not path.is_file():
        return _miss("SMC structure snapshot not exported ΓÇö " + _SMC_EXPORT_HINT.format(symbol=clean_sym, tf=tf))
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            raise ValueError("snapshot is not an object")
    except Exception as exc:
        return _miss(f"unreadable snapshot: {exc}")
    data.setdefault("symbol", clean_sym)
    data.setdefault("timeframe", tf)
    data["disclosure"] = data.get("disclosure") or _SMC_DISCLOSURE
    return data


def build_forecast_band(symbol: str, horizon: int = 5, history_bars: int = 45) -> Dict[str, Any]:
    """
    ADR-0012 ┬º4: a Kronos-mini forecast band on DAILY bars (the only cadence the
    model was validated on), rendered as a clearly-labelled research preview with
    the failed-verdict disclosure attached. Fail-closed: missing torch/weights, any
    inference error, or thin history returns {"available": False, "reason": ...} ΓÇö
    the band is NEVER fabricated. Cached (TTL 1h) so inference stays off the hot path.
    """
    import time as _time

    import pandas as pd

    with _FORECAST_CACHE_LOCK:
        clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
        horizon = max(1, min(int(horizon), 10))
        key = (clean_sym, horizon)

        def _miss(reason: Any) -> Dict[str, Any]:
            text = str(reason).strip()
            if not text:  # an exception with an empty message must still explain itself
                text = type(reason).__name__ if isinstance(reason, BaseException) else "unknown reason"
            return {"available": False, "symbol": clean_sym, "reason": text, "disclosure": _KRONOS_VERDICT}

        hit = _FORECAST_CACHE.get(key)
        if hit and (_time.time() - hit["_ts"]) < _FORECAST_CACHE_TTL_S:
            return hit["payload"]

        try:
            from mjonai.data.angelone.historical import CandleInterval, fetch_historical_candles
            df = fetch_historical_candles(clean_sym, interval=CandleInterval.ONE_DAY, days_back=520)
        except Exception as exc:  # fetch failure is an honest miss, not a fabricated band
            return _miss(f"candle fetch failed: {exc}")
        if df is None or getattr(df, "empty", True) or len(df) < 120:
            return _miss("insufficient daily history")

        def _col(caps: str):
            if caps in df:
                return df[caps]
            if caps.lower() in df:
                return df[caps.lower()]
            return None

        o, h, l, c = _col("Open"), _col("High"), _col("Low"), _col("Close")
        v = _col("Volume")
        if o is None or h is None or l is None or c is None:
            return _miss("unexpected candle columns")
        frame = pd.DataFrame(
            {"Open": o, "High": h, "Low": l, "Close": c, "Volume": v if v is not None else 0.0},
            index=df.index,
        ).dropna()
        if len(frame) < 120:
            return _miss("insufficient clean daily history")

        try:
            from mjonai.research.forecasting.kronos_adapter import KronosModel
            model = KronosModel(size="mini")
            result = model.predict(frame.tail(400), horizon=horizon)
            q = result.quantiles
        except Exception as exc:  # torch/weights absent, or inference failed ΓÇö fail closed
            return _miss(exc)

        levels = sorted(k for k in q if isinstance(k, (int, float)))
        if not levels:
            return _miss("model returned no quantiles")
        lower = [float(x) for x in q[levels[0]]]
        upper = [float(x) for x in q[levels[-1]]]
        median = [float(x) for x in (q.get(0.5) or q.get(levels[len(levels) // 2]) or [])]
        if not (len(lower) == len(upper) == len(median) == horizon):
            return _miss("model returned malformed quantile paths")

        idx = pd.DatetimeIndex(frame.index)
        step = idx[-1] - idx[-2] if len(idx) >= 2 else pd.Timedelta(days=1)
        hist = frame.tail(history_bars)
        payload = {
            "available": True,
            "symbol": clean_sym,
            "model": model.name,
            "horizon": horizon,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "history": [
                {"time": int(ts.timestamp()), "close": round(float(cl), 2)}
                for ts, cl in zip(pd.DatetimeIndex(hist.index), hist["Close"])
            ],
            "path": {
                "time": [int((idx[-1] + step * (i + 1)).timestamp()) for i in range(horizon)],
                "lower": [round(x, 2) for x in lower],
                "median": [round(x, 2) for x in median],
                "upper": [round(x, 2) for x in upper],
            },
            "disclosure": _KRONOS_VERDICT,
        }
        _FORECAST_CACHE[key] = {"_ts": _time.time(), "payload": payload}
        return payload


# ─── FinViz-pattern Sector Heatmap (treemap) ──────
def build_sector_heatmap(min_bars: int = 60) -> Optional[Dict[str, Any]]:
    """
    Sector heatmap (treemap) over the local equity panel.

    Groups the panel by NSE sector, computes per-sector average change and
    breadth. Uses ECharts treemap format: each sector is a rectangle sized by
    symbol count, colored by average 1d change (green = up, red = down).

    Fail-closed: missing panel or no symbols with sector data returns None.
    """
    try:
        from mjonai.research.data.market_overview import load_symbol_summaries
    except Exception:
        return None

    try:
        df = load_symbol_summaries(min_bars=min_bars)
    except Exception:
        return None
    if df.empty:
        return None

    # Add sector mapping
    df["sector"] = df["symbol"].apply(_get_sector)

    with_chg = df[df["chg_pct"].notna()]
    if with_chg.empty:
        return None

    sectors = []
    for sector_name, group in with_chg.groupby("sector"):
        count = len(group)
        avg_chg = float(group["chg_pct"].mean())
        adv = int((group["chg_pct"] > 0).sum())
        dec = int((group["chg_pct"] < 0).sum())
        # Size by symbol count, color by avg change
        sectors.append({
            "name": sector_name,
            "value": round(avg_chg, 2),  # average 1d change %
            "count": count,
            "advancing": adv,
            "declining": dec,
            "breadth_pct": round(100.0 * adv / count, 1) if count else 0,
        })

    # Sort by absolute average change (most action first)
    sectors.sort(key=lambda s: abs(s["value"]), reverse=True)

    return {
        "available": True,
        "as_of": None,
        "sectors": sectors,
        "total_symbols": int(len(with_chg)),
        "disclosure": (
            "RESEARCH DATA VIEW — sector heatmap computed from MJONAI's own Yahoo-sourced "
            "equity panel (497 symbols). Sector mapping is a static clean-room dictionary. "
            "Not a signal, no edge claim; the newest bar is the panel's last bar, which may be stale."
        ),
    }


# ─── FinViz Filter Maps (auto-generated from FinViz screener) ──────
def build_signal_filters() -> Dict[str, Any]:
    """
    Return the auto-generated FinViz filter maps (signals, exchange, index, sector, etc.).
    Clean-room reimplementation of knicola/finviz-screener's generate.js.
    """
    try:
        from mjonai.data.finviz_filters import (
            signalsMap,
            exchangeMap,
            sectorMap,
            technicalMap,
            fundamentalMap,
            ownershipMap,
            market_capMap,
            otherMap,
        )
    except Exception:
        # Fallback to minimal hardcoded maps if generation hasn't run
        return {
            "available": False,
            "reason": "FinViz filters not generated — run apps/scripts/generate_finviz_filters.py",
            "signalsMap": {},
            "exchangeMap": {},
            "sectorMap": {},
            "technicalMap": {},
            "fundamentalMap": {},
            "ownershipMap": {},
            "marketCapMap": {},
            "otherMap": {},
        }

    return {
        "available": True,
        "signalsMap": signalsMap,
        "exchangeMap": exchangeMap,
        "sectorMap": sectorMap,
        "technicalMap": technicalMap,
        "fundamentalMap": fundamentalMap,
        "ownershipMap": ownershipMap,
        "marketCapMap": market_capMap,
        "otherMap": otherMap,
        "disclosure": (
            "RESEARCH DATA VIEW — FinViz filter taxonomy auto-generated from FinViz screener. "
            "Clean-room reimplementation of knicola/finviz-screener's generate.js. "
            "Not a signal, no edge claim; mappings are descriptive only."
        ),
    }


# ─── FRED Macro Fallback (US macro series from FRED) ──────
def build_fred_macro() -> Dict[str, Any]:
    """
    Fetch US macro series from FRED fallback provider.
    Fail-closed: returns available=False if FRED_API_KEY not configured.
    Not a signal, descriptive analytics only.
    """
    try:
        from mjonai.data.fred_fallback import FredFallbackProvider
    except Exception:
        return {"available": False, "reason": "FRED fallback module not available"}

    provider = FredFallbackProvider()
    if not provider.feed_available:
        return {"available": False, "reason": "FRED_API_KEY not configured"}

    result = provider.fetch_us_macro()
    result["disclosure"] = (
        "RESEARCH DATA VIEW — US macro series from FRED (Federal Reserve Economic Data). "
        "Fail-closed: requires FRED_API_KEY. Not a signal, no edge claim."
    )
    return result
