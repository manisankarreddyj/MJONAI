"""JSON API routes — every handler delegates to app.data_views (facade-only)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from apps.web.auth import verify_api_token
from apps.web.data_views import (
    _OPTIONS_DISCLOSURE,
    build_ai_debates,
    build_equity_series,
    build_forecast_band,
    build_market_cockpit,
    build_open_trades,
    build_option_chain,
    build_option_payoff,
    build_console_queue,
    build_recent_trades,
    build_signal_track_record,
    build_smc_structure,
    build_stock_candles,
    build_strategy_performance,
    build_system_status,
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
