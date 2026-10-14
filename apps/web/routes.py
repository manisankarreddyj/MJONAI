"""JSON API routes — every handler delegates to app.data_views (facade-only)."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, Query

from apps.web.auth import verify_api_token
from apps.web.data_views import (
    build_fred_macro,
    _OPTIONS_DISCLOSURE,
    build_ai_debates,
    build_equity_series,
    build_forecast_band,
    build_market_cockpit,
    build_market_overview,
    build_open_trades,
    build_option_chain,
    build_option_payoff,
    build_console_queue,
    build_dbnomics_series,
    build_evidence_compare,
    build_research_index,
    build_recent_trades,
    build_sector_heatmap,
    build_signal_filters,
    build_signal_track_record,
    build_smc_structure,
    build_stock_candles,
    build_strategy_performance,
    build_system_status,
    build_tca,
    build_today_signals,
    build_trade_history,
    record_console_decision,
)

router = APIRouter(prefix="/api", dependencies=[Depends(verify_api_token)])


@router.get("/status")
def status_view() -> dict:
    return build_system_status()


@router.get("/market/cockpit")
def market_cockpit_view() -> dict:
    return build_market_cockpit()


@router.get("/trades/open")
def open_trades_view() -> dict:
    return {"trades": build_open_trades(), "count": len(build_open_trades())}


@router.get("/trades/closed-today")
def closed_today_view(
    limit: int = Query(default=20, ge=1, le=200),
) -> dict:
    rows = build_recent_trades(limit)
    return {"trades": rows, "count": len(rows)}


@router.get("/signals/today")
def signals_today_view(
    limit: int = Query(default=25, ge=1, le=200),
) -> dict:
    rows = build_today_signals(limit)
    return {"signals": rows, "count": len(rows)}


@router.get("/trades/history")
def trades_history_view(
    days: int = Query(default=30, ge=1, le=365),
    limit: int = Query(default=200, ge=1, le=1000),
) -> dict:
    rows = build_trade_history(days=days, limit=limit)
    return {"trades": rows, "count": len(rows)}


@router.get("/performance/strategies")
def strategy_performance_view(
    days: int = Query(default=90, ge=1, le=365),
) -> dict:
    rows = build_strategy_performance(days=days)
    return {"strategies": rows, "count": len(rows)}


@router.get("/equity")
def equity_view(
    days: int = Query(default=30, ge=1, le=365),
    system_mode: Optional[str] = Query(default=None),
) -> dict:
    return {"series": build_equity_series(days=days, system_mode=system_mode)}


@router.get("/market/candles")
def stock_candles_view(
    symbol: str = Query(..., min_length=1),
    timeframe: str = Query(default="15m"),
    days: int = Query(default=5, ge=1, le=30),
) -> dict:
    return build_stock_candles(symbol=symbol, timeframe=timeframe, days_back=days)


@router.get("/signals/debates")
def signals_debates_view(
    limit: int = Query(default=20, ge=1, le=100),
) -> dict:
    rows = build_ai_debates(limit=limit)
    return {"debates": rows, "count": len(rows)}


@router.get("/signals/track-record")
def signals_track_record_view(
    days: int = Query(default=90, ge=1, le=365),
) -> dict:
    return build_signal_track_record(days=days)


@router.get("/signals/forecast")
def signals_forecast_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    horizon: int = Query(default=5, ge=1, le=10),
) -> dict:
    """ADR-0012 research preview: Kronos-mini forecast band on daily bars, with the
    failed-verdict disclosure attached. Fail-closed: an unavailable model returns
    {"available": false, "reason": ...} — never a fabricated band."""
    return build_forecast_band(symbol=symbol, horizon=horizon)


@router.get("/console/queue")
def console_queue_view(limit: int = Query(default=12, ge=1, le=50)) -> dict:
    """Approval console: the engine's approved-but-unexecuted decisions awaiting the
    operator's MANUAL execution (advisory only — no orders, ADR-0007)."""
    return build_console_queue(limit=limit)


@router.post("/console/decision")
async def console_decision_view(payload: dict, _auth: None = Depends(verify_api_token)) -> dict:
    """Journal an operator disposition (APPROVED_FOR_MANUAL / REJECTED / SNOOZED) to
    the system_log telemetry journal. Telemetry only: no order is ever placed."""
    return record_console_decision(
        signal_id=str(payload.get("signal_id") or ""),
        action=str(payload.get("action") or ""),
        note=str(payload.get("note") or ""),
    )


@router.get("/market/overview")
def market_overview_view(top: int = Query(default=8, ge=1, le=25)) -> dict:
    """Finviz-pattern market overview: breadth strip, top gainers/losers, unusual
    volume, new highs/lows and heatmap rows — descriptive analytics over the local
    equity panel, fail-closed when the panel is absent. Not a signal."""
    return build_market_overview(top=top)


@router.get("/market/sector-heatmap")
def market_sector_heatmap_view(min_bars: int = Query(default=60, ge=10, le=500)) -> dict:
    """Finviz-pattern sector treemap: groups the equity panel by NSE sector,
    sizes by symbol count, colors by average 1d change. Descriptive analytics
    over the local panel — fail-closed when panel absent. Not a signal."""
    return build_sector_heatmap(min_bars=min_bars) or {"available": False, "reason": "equity panel empty or absent"}


@router.get("/market/fred-macro")
def market_fred_macro_view() -> dict:
    """US macro series from FRED fallback provider.
    Fail-closed: returns available=False if FRED_API_KEY not configured.
    Not a signal, descriptive analytics only."""
    return build_fred_macro()



@router.get("/market/dbnomics")
def market_dbnomics_view(
    provider: str = Query(default="", max_length=32),
    dataset: str = Query(default="", max_length=64),
    series: str = Query(default="", max_length=64),
) -> dict:
    """One macro observation from the keyless DBnomics API (explicit codes only).
    Fail-closed on blank codes or any fetch failure. Descriptive only."""
    return build_dbnomics_series(provider=provider, dataset=dataset, series=series)


@router.get("/market/signal-filters")
def market_signal_filters_view() -> dict:
    """FinViz filter taxonomy maps (signals, exchange, index, sector, industry, etc.).
    Auto-generated from FinViz screener via knicola/finviz-screener clean-room reimplementation.
    Descriptive only — not a signal, fail-closed if generation hasn't run."""
    return build_signal_filters()


@router.get("/journal/evidence")
def journal_evidence_view(limit: int = Query(default=40, ge=1, le=200)) -> dict:
    """Bloomberg-research-management analog: the persisted verdict-artifact index."""
    return build_research_index(limit=limit)


@router.get("/journal/evidence/compare")
def journal_evidence_compare_view(files: List[str] = Query(default=[])) -> dict:
    """Run-vs-run metric comparison over recorded verdict artifacts (read-only).
    Basenames only (?files=a.json&files=b.json, up to 4); nothing recomputed."""
    return build_evidence_compare(files)


@router.get("/analytics/tca")
def analytics_tca_view(limit: int = Query(default=200, ge=1, le=2000)) -> dict:
    """Bloomberg-TCA analog: realized cost/slippage analytics from our own ledger —
    the honest 'what did this trade actually cost' view."""
    return build_tca(limit=limit)


@router.get("/options/chain")
def options_chain_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    strikes: int = Query(default=7, ge=1, le=25),
) -> dict:
    """Options desk #1: chain + window PCR + max pain + OI profile from the official
    F&O warehouse. Descriptive research display only (no signal, no orders);
    fail-closed when the warehouse has no rows for the symbol/date."""
    return build_option_chain(symbol=symbol, as_of=as_of, strikes=strikes)


@router.get("/options/payoff")
def options_payoff_view(
    legs: Optional[str] = Query(default=None, description="JSON list of {type,side,strike,premium,lots}"),
    spot: Optional[float] = Query(default=None),
    ce_strike: Optional[float] = Query(default=None),
    pe_strike: Optional[float] = Query(default=None),
    ce_premium: Optional[float] = Query(default=None),
    pe_premium: Optional[float] = Query(default=None),
    side: str = Query(default="BUY", max_length=8),
    lot_size: int = Query(default=25, ge=1, le=10_000),
    points: int = Query(default=41, ge=11, le=201),
    span_pct: float = Query(default=0.10, gt=0, le=1.0),
) -> dict:
    """Options desk #2: expiry payoff diagrams + straddle PnL. Pure math — no market
    data, no signals; malformed input fails closed with a reason."""
    import json as _json

    parsed_legs = None
    if legs:
        try:
            parsed_legs = _json.loads(legs)
            if not isinstance(parsed_legs, list) or not parsed_legs:
                raise ValueError("legs must be a non-empty JSON list")
        except Exception as exc:
            return {"available": False, "reason": f"legs parse failed: {exc}",
                    "disclosure": _OPTIONS_DISCLOSURE}
    straddle = None
    if spot is not None and None not in (ce_strike, pe_strike, ce_premium, pe_premium):
        straddle = {"spot": spot, "ce_strike": ce_strike, "pe_strike": pe_strike,
                    "ce_premium": ce_premium, "pe_premium": pe_premium, "side": side}
    return build_option_payoff(legs=parsed_legs, straddle=straddle,
                               points=points, span_pct=span_pct, lot_size=lot_size)


@router.get("/options/strategy")
def options_strategy_view(
    spot: float = Query(..., gt=0),
    legs: str = Query(..., description="JSON list of {type,side,strike,premium,lots,label}"),
    lot_size: int = Query(default=25, ge=1, le=10_000),
) -> dict:
    """Options desk #12: strategy builder — multi-leg payoff at expiry.
    Pure math, no market data. Returns payoff curve, breakevens, max profit/loss."""
    import json as _json
    from mjonai.research.data.option_desk import strategy_builder

    try:
        parsed_legs = _json.loads(legs)
        if not isinstance(parsed_legs, list) or not parsed_legs:
            raise ValueError("legs must be a non-empty JSON list")
        for leg in parsed_legs:
            if not all(k in leg for k in ("type", "side", "strike", "premium", "lots")):
                raise ValueError("each leg requires type, side, strike, premium, lots")
    except Exception as exc:
        return {"available": False, "reason": f"legs parse/validate failed: {exc}",
                "disclosure": _OPTIONS_DISCLOSURE}
    return {"available": True, **strategy_builder(spot=spot, legs=parsed_legs, lot_size=lot_size)}


@router.get("/options/portfolio")
def options_portfolio_list_view() -> dict:
    """Options desk #11: saved strategy-builder leg sets (local persistence)."""
    from mjonai.research.data.strategy_portfolio import list_entries
    try:
        entries = list_entries()
    except Exception as exc:
        return {"available": False, "reason": f"portfolio unavailable: {exc}",
                "disclosure": _OPTIONS_DISCLOSURE}
    return {"available": True, "entries": entries, "disclosure": _OPTIONS_DISCLOSURE}


@router.post("/options/portfolio")
async def options_portfolio_save_view(payload: dict) -> dict:
    """Save (or overwrite) one named leg set. Stores builder inputs for replay
    only — never executes, never prices. Malformed legs fail closed."""
    from mjonai.research.data.strategy_portfolio import save_entry
    try:
        record = save_entry(
            name=str(payload.get("name") or ""),
            label=str(payload.get("label") or ""),
            spot=payload.get("spot"),
            legs=payload.get("legs"),
            lot_size=payload.get("lot_size", 25),
        )
    except Exception as exc:
        return {"available": False, "reason": f"save refused: {exc}",
                "disclosure": _OPTIONS_DISCLOSURE}
    return {"available": True, "entry": record, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/portfolio/{name}")
def options_portfolio_get_view(name: str) -> dict:
    """Fetch one saved leg set by name for replay in the builder."""
    from mjonai.research.data.strategy_portfolio import get_entry
    record = get_entry(name)
    if record is None:
        return {"available": False, "reason": f"no saved strategy {name!r}",
                "disclosure": _OPTIONS_DISCLOSURE}
    return {"available": True, "entry": record, "disclosure": _OPTIONS_DISCLOSURE}


@router.delete("/options/portfolio/{name}")
def options_portfolio_delete_view(name: str) -> dict:
    """Delete one saved leg set. Missing names fail closed, never silently ok."""
    from mjonai.research.data.strategy_portfolio import delete_entry
    if not delete_entry(name):
        return {"available": False, "reason": f"no saved strategy {name!r}",
                "disclosure": _OPTIONS_DISCLOSURE}
    return {"available": True, "deleted": name, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/smile")
def options_smile_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    strikes: int = Query(default=7, ge=1, le=25),
) -> dict:
    """Options desk #9: IV smile per strike (CE/PE) — standalone slice of the chain."""
    from mjonai.research.data.fno_eod import load_eod_chain_for_date
    from mjonai.research.data.option_desk import chain_window, iv_smile
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR
    import pandas as pd

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    try:
        ts = pd.Timestamp(as_of).normalize()
        frame = load_eod_chain_for_date(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts)
    except Exception as exc:
        return {"available": False, "reason": f"chain read failed: {exc}"}
    if frame is None:
        return {"available": False, "reason": f"no chain for {clean_sym} on {as_of}"}
    win = chain_window(frame, n_strikes=max(1, min(int(strikes), 25)))
    if not win["rows"]:
        return {"available": False, "reason": "chain window empty"}
    dte_days = max(0, (pd.Timestamp(min(pd.to_datetime(frame["expiry"]))).normalize() - ts).days)
    smile = iv_smile(win["rows"], win["spot"], dte_days)
    return {"available": True, "symbol": clean_sym, "as_of": as_of, "spot": win["spot"],
            "dte_days": dte_days, "iv_smile": smile, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/gex")
def options_gex_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    strikes: int = Query(default=7, ge=1, le=25),
) -> dict:
    """Options desk #11: GEX dashboard — dealer gamma exposure per strike."""
    from mjonai.research.data.fno_eod import load_eod_chain_for_date
    from mjonai.research.data.option_desk import chain_window, iv_smile, gex_profile
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR
    import pandas as pd

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    try:
        ts = pd.Timestamp(as_of).normalize()
        frame = load_eod_chain_for_date(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts)
    except Exception as exc:
        return {"available": False, "reason": f"chain read failed: {exc}"}
    if frame is None:
        return {"available": False, "reason": f"no chain for {clean_sym} on {as_of}"}
    win = chain_window(frame, n_strikes=max(1, min(int(strikes), 25)))
    if not win["rows"]:
        return {"available": False, "reason": "chain window empty"}
    dte_days = max(0, (pd.Timestamp(min(pd.to_datetime(frame["expiry"]))).normalize() - ts).days)
    smile = iv_smile(win["rows"], win["spot"], dte_days)
    gex = gex_profile(frame, win["rows"], smile, win["spot"], dte_days)
    return {"available": gex is not None, "symbol": clean_sym, "as_of": as_of,
            "spot": win["spot"], "dte_days": dte_days, "gex": gex, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/oi-tracker")
def options_oi_tracker_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    strikes: int = Query(default=7, ge=1, le=25),
) -> dict:
    """Options desk #12a: OI tracker — per-strike OI change (buildup/unwinding)."""
    from mjonai.research.data.fno_eod import load_eod_chain_for_date
    from mjonai.research.data.option_desk import chain_window, oi_track
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR
    import pandas as pd

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    try:
        ts = pd.Timestamp(as_of).normalize()
        frame = load_eod_chain_for_date(DEFAULT_FNO_CHAIN_DIR, clean_sym, ts)
    except Exception as exc:
        return {"available": False, "reason": f"chain read failed: {exc}"}
    if frame is None:
        return {"available": False, "reason": f"no chain for {clean_sym} on {as_of}"}
    win = chain_window(frame, n_strikes=max(1, min(int(strikes), 25)))
    if not win["rows"]:
        return {"available": False, "reason": "chain window empty"}
    tracker = oi_track(win["rows"])
    return {"available": True, "symbol": clean_sym, "as_of": as_of,
            "spot": win["spot"], "oi_tracker": tracker, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/vol-surface")
def options_vol_surface_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    strikes: int = Query(default=7, ge=1, le=25),
    expiries: int = Query(default=2, ge=1, le=4),
) -> dict:
    """Options desk #10: IV surface across nearest expiries."""
    from mjonai.research.data.option_desk import vol_surface
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    surface = vol_surface(DEFAULT_FNO_CHAIN_DIR, clean_sym, as_of,
                          n_strikes=max(1, min(int(strikes), 25)),
                          max_expiries=max(1, int(expiries)))
    return {"available": surface is not None, "symbol": clean_sym, "as_of": as_of,
            "vol_surface": surface, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/oi-history")
def options_oi_history_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    expiry: str = Query(..., description="YYYY-MM-DD expiry date"),
    strikes: int = Query(default=5, ge=1, le=25),
    lookback: int = Query(default=10, ge=1, le=60),
) -> dict:
    """Options desk #12b: OI history for one expiry across trading days."""
    from mjonai.research.data.option_desk import oi_history
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    history = oi_history(DEFAULT_FNO_CHAIN_DIR, clean_sym, as_of, expiry,
                         n_strikes=max(1, min(int(strikes), 25)),
                         lookback_days=max(1, int(lookback)))
    return {"available": history is not None, "symbol": clean_sym, "as_of": as_of,
            "expiry": expiry, "oi_history": history, "disclosure": _OPTIONS_DISCLOSURE}
@router.get("/options/greeks-history")
def options_greeks_history_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    expiry: str = Query(..., description="YYYY-MM-DD expiry date"),
    lookback: int = Query(default=10, ge=1, le=60),
) -> dict:
    """Options desk #9: ATM Greeks history for one expiry across trading days."""
    from mjonai.research.data.option_desk import greeks_history
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    history = greeks_history(DEFAULT_FNO_CHAIN_DIR, clean_sym, as_of, expiry,
                             lookback_days=max(1, int(lookback)))
    return {"available": history is not None, "symbol": clean_sym, "as_of": as_of,
            "expiry": expiry, "greeks_history": history, "disclosure": _OPTIONS_DISCLOSURE}


@router.get("/options/straddle-series")
def options_straddle_series_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    as_of: str = Query(..., description="YYYY-MM-DD trading date"),
    expiry: str = Query(..., description="YYYY-MM-DD expiry date"),
    lookback: int = Query(default=10, ge=1, le=60),
) -> dict:
    """Options desk #10: daily ATM-straddle series + futures overlay (when owned)."""
    from mjonai.research.data.option_desk import straddle_series
    from mjonai.research.registry_adapter import DEFAULT_FNO_CHAIN_DIR

    clean_sym = symbol.upper().replace(".NS", "").replace(".BO", "")
    series = straddle_series(DEFAULT_FNO_CHAIN_DIR, clean_sym, as_of, expiry,
                             lookback_days=max(1, int(lookback)))
    return {"available": series is not None, "symbol": clean_sym, "as_of": as_of,
            "expiry": expiry, "straddle_series": series, "disclosure": _OPTIONS_DISCLOSURE}


def market_smc_structure_view(
    symbol: str = Query(..., min_length=1, max_length=32),
    timeframe: str = Query(default="1d", max_length=4),
) -> dict:
    """Research-preview SMC structure markers (ADR-0013): reads the snapshot the
    research-tier CLI exported. The fence forbids apps/web from importing
    mjonai.research.discovery, so this view reads DATA, never computes it — and an
    un-exported snapshot renders as available=false, never fabricated markers."""
    return build_smc_structure(symbol=symbol, timeframe=timeframe)


@router.get("/stream/live")
async def live_stream_view():
    """Real-Time Server-Sent Events (SSE) push stream for market cockpit and active trades."""
    import asyncio
    import json
    from fastapi.responses import StreamingResponse

    async def event_generator():
        for _ in range(300):  # Stream for up to 10 minutes per connection
            try:
                cockpit = build_market_cockpit()
                trades = build_open_trades()
                payload = {
                    "market": cockpit,
                    "open_trades_count": len(trades),
                    "open_trades": trades,
                }
                yield f"data: {json.dumps(payload)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(2.0)

    return StreamingResponse(event_generator(), media_type="text/event-stream")
