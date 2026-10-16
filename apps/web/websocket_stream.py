"""
Module: app/websocket_stream.py
Purpose: SOTA Real-Time WebSocket Streaming Gateway for Desktop Mission Control & Mobile Commander.
         Broadcasts live ticks, MTM portfolio valuation, active trade updates,
         AI specialist boardroom deliberation streams, and system health telemetry.
"""

import asyncio
import json
import logging
import time
from typing import Dict, Any, List, Set
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from apps.web.auth import verify_api_token
from mjonai.core.time_utils import now_ist
from apps.runtime.orchestration.market_session_lifecycle import get_current_session_state
from apps.runtime.orchestration.system_readiness import evaluate_system_readiness

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket Streaming"])

# Throttled snapshot observability: the WS ticks every 500ms, so a per-tick
# INFO line would flood web.log (~7k lines/hour). Log a one-line summary at
# most every _SNAPSHOT_LOG_EVERY_S seconds instead — count/total/stale —
# so the terminal feed is observable in logs/YYYY-MM-DD/web.log like the
# engine is in engine.log.
_SNAPSHOT_LOG_EVERY_S = 60.0
_last_snapshot_log_ts = 0.0


class WebSocketHub:
    """Thread-safe and async-safe WebSocket connection manager."""
    def __init__(self):
        self.active_connections: Set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)
        logger.info(f"[WebSocketHub] Client connected. Active clients: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket) -> None:
        async with self._lock:
            self.active_connections.discard(websocket)
        logger.info(f"[WebSocketHub] Client disconnected. Active clients: {len(self.active_connections)}")

    async def broadcast(self, message: Dict[str, Any]) -> None:
        if not self.active_connections:
            return

        payload = json.dumps(message)
        dead_connections: List[WebSocket] = []

        async with self._lock:
            for ws in list(self.active_connections):
                try:
                    await ws.send_text(payload)
                except Exception:
                    dead_connections.append(ws)

            for dead_ws in dead_connections:
                self.active_connections.discard(dead_ws)


STREAM_HUB = WebSocketHub()


def _safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def _safe_int(val: Any, default: int = 1) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def get_live_telemetry_snapshot() -> Dict[str, Any]:
    """Compile an instantaneous full-system telemetry snapshot for streaming.

    Single source of truth: reuses ``apps.web.data_views.build_open_trades``
    (freshness-gated LTP + direction-adjusted unrealized) instead of reading
    raw DB columns (``current_price``/``pnl`` don't exist on the trades row —
    the old path fell back to entry-as-LTP and booked 0.0 on every row).
    ``fetch_historical_candles`` inside the builder is RAM-TTL cached (60s),
    so the 500ms WS cadence mostly hits cache, same as the /api/stream/live
    SSE path which already calls the builder every 2s.
    """
    state = get_current_session_state()
    readiness = evaluate_system_readiness()
    from apps.web.data_views import build_open_trades

    try:
        enriched = build_open_trades() or []
    except Exception:
        enriched = []

    total_unrealized_pnl = round(
        sum(t.get("unrealized_pnl") for t in enriched if t.get("unrealized_pnl") is not None),
        2,
    )
    used_capital = sum(
        _safe_float(t.get("entry_price")) * _safe_int(t.get("quantity")) for t in enriched
    )
    from mjonai.core.constants import TOTAL_CAPITAL
    margin_utilization_pct = round((used_capital / TOTAL_CAPITAL) * 100, 2) if TOTAL_CAPITAL > 0 else 0.0
    daily_drawdown_pct = round(min(0.0, (total_unrealized_pnl / TOTAL_CAPITAL) * 100), 2) if TOTAL_CAPITAL > 0 else 0.0

    snapshot = {
        "type": "TELEMETRY_PULSE",
        "timestamp": now_ist().isoformat(),
        "session_state": state.value,
        "operational_tier": readiness.tier.value,
        "sizing_multiplier": readiness.sizing_multiplier,
        "open_trades_count": len(enriched),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "margin_utilization_pct": margin_utilization_pct,
        "daily_drawdown_pct": daily_drawdown_pct,
        "open_trades": [
            {
                "id": str(t.get("id")),
                "symbol": t.get("symbol") or "UNKNOWN",
                "direction": t.get("side", "BUY"),
                "entry_price": _safe_float(t.get("entry_price")),
                # Display continuity: stale rows show entry flat AND stale:true
                # (labelled, never silently booked). Live rows carry the real LTP.
                "current_price": _safe_float(
                    t.get("current_price")
                    if t.get("current_price") is not None
                    else t.get("entry_price")
                ),
                "stale": bool(t.get("stale", t.get("current_price") is None)),
                "price_source": t.get("price_source"),
                "stop_loss": _safe_float(t.get("stop_loss")),
                "trailing_stop": _safe_float(t.get("stop_loss")),
                "target_1": _safe_float(t.get("target_1") if t.get("target_1") is not None else t.get("target")),
                "pnl": _safe_float(t.get("unrealized_pnl"), default=0.0),
                "pnl_pct": _safe_float(t.get("unrealized_pct"), default=0.0),
                "strategy": t.get("strategy_id", "S01"),
                # Holding horizon, display-only (may be null — the blotter
                # renders "—", never a fabricated ETA).
                "holding_window_min": t.get("holding_window_min"),
                "holding_window_max": t.get("holding_window_max"),
                "eta_min": t.get("expected_days_min"),
                "eta_max": t.get("expected_days_max"),
                # Measured medians (null when the snapshot is absent/thin —
                # the blotter renders "—", never a fabricated median).
                "measured_days_median": t.get("measured_days_median"),
                "measured_n_target": t.get("measured_n_target"),
            }
            for t in enriched
        ],
        "audit_events": [
            f"{now_ist().strftime('%H:%M:%S')} IST | System Health: {readiness.tier.value} | Sizing: {readiness.sizing_multiplier}x",
            f"{now_ist().strftime('%H:%M:%S')} IST | Session State: {state.value} | Active Scanners Online",
        ],
    }

    # Throttled observability line for web.log (max 1/60s — never per-tick).
    try:
        global _last_snapshot_log_ts
        now_s = time.time()
        if now_s - _last_snapshot_log_ts >= _SNAPSHOT_LOG_EVERY_S:
            _last_snapshot_log_ts = now_s
            stale_n = sum(1 for t in snapshot["open_trades"] if t.get("stale"))
            logger.info(
                "[ws/stream] pulse n=%d total_pnl=%s stale=%d margin=%s%% dd=%s%%",
                snapshot["open_trades_count"],
                snapshot["total_unrealized_pnl"],
                stale_n,
                margin_utilization_pct,
                daily_drawdown_pct,
            )
    except Exception:
        pass  # observability must never break the stream

    return snapshot


@router.websocket("/ws/stream", dependencies=[Depends(verify_api_token)])
async def websocket_stream_endpoint(websocket: WebSocket) -> None:
    """High-frequency streaming endpoint for Web Terminal & Mobile Commander."""
    await STREAM_HUB.connect(websocket)
    try:
        # Send initial snapshot immediately upon connection
        init_snapshot = get_live_telemetry_snapshot()
        await websocket.send_text(json.dumps(init_snapshot))

        while True:
            # Handle incoming client messages (e.g. ping or client heartbeat)
            try:
                msg = await asyncio.wait_for(websocket.receive_text(), timeout=0.5)
                # Client heartbeats / pings can be acknowledged
                if msg == "ping":
                    await websocket.send_text(json.dumps({"type": "PONG", "timestamp": now_ist().isoformat()}))
                elif msg == "close":
                    break
            except asyncio.TimeoutError:
                pass

            # Stream periodic telemetry update. Cadence is 5s BY DESIGN: the
            # underlying LTP inputs are 60s-TTL cached (plus a single-flight
            # guard), so a 500ms loop re-fires 29 symbols × 2 intervals of
            # fetches ~120× per TTL window for zero new information (web.log
            # 2026-10-16: 4k+ duplicate yfinance fetches/day). 5s still feels
            # live on the blotter at one-tenth the load.
            update = get_live_telemetry_snapshot()
            await websocket.send_text(json.dumps(update))
            await asyncio.sleep(5.0)  # 5s update cadence

    except WebSocketDisconnect:
        await STREAM_HUB.disconnect(websocket)
    except Exception as e:
        logger.warning(f"[WebSocketStream] Client connection error: {e}")
        await STREAM_HUB.disconnect(websocket)
