"""JSON API routes — every handler delegates to app.data_views (facade-only)."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query

from apps.web.auth import verify_api_token
from apps.web.data_views import (
    build_ai_debates,
    build_equity_series,
    build_market_cockpit,
    build_open_trades,
    build_recent_trades,
    build_stock_candles,
    build_strategy_performance,
    build_system_status,
    build_today_signals,
    build_trade_history,
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
