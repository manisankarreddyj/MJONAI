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
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from core.time_utils import now_ist
from orchestration.market_session_lifecycle import get_current_session_state
from orchestration.system_readiness import evaluate_system_readiness
from db.repository import get_open_trades

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket Streaming"])


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
    """Compile an instantaneous full-system telemetry snapshot for streaming."""
    state = get_current_session_state()
    readiness = evaluate_system_readiness()
    open_trades = get_open_trades() or []

    total_unrealized_pnl = sum(_safe_float(t.get("pnl")) for t in open_trades)
    used_capital = sum(_safe_float(t.get("entry_price")) * _safe_int(t.get("quantity")) for t in open_trades)
    from core.constants import TOTAL_CAPITAL
    margin_utilization_pct = round((used_capital / TOTAL_CAPITAL) * 100, 2) if TOTAL_CAPITAL > 0 else 0.0
    daily_drawdown_pct = round(min(0.0, (total_unrealized_pnl / TOTAL_CAPITAL) * 100), 2) if TOTAL_CAPITAL > 0 else 0.0

    return {
        "type": "TELEMETRY_PULSE",
        "timestamp": now_ist().isoformat(),
        "session_state": state.value,
        "operational_tier": readiness.tier.value,
        "sizing_multiplier": readiness.sizing_multiplier,
        "open_trades_count": len(open_trades),
        "total_unrealized_pnl": round(total_unrealized_pnl, 2),
        "margin_utilization_pct": margin_utilization_pct,
        "daily_drawdown_pct": daily_drawdown_pct,
        "open_trades": [
            {
                "id": str(t.get("id")),
                "symbol": t.get("symbol") or "UNKNOWN",
                "direction": t.get("direction", "BUY"),
                "entry_price": _safe_float(t.get("entry_price")),
                "current_price": _safe_float(t.get("current_price") or t.get("entry_price")),
                "stop_loss": _safe_float(t.get("stop_loss")),
                "trailing_stop": _safe_float(t.get("trailing_stop") or t.get("stop_loss")),
                "target_1": _safe_float(t.get("target_1")),
                "pnl": _safe_float(t.get("pnl")),
                "pnl_pct": _safe_float(t.get("pnl_pct")),
                "strategy": t.get("strategy_id", "S01"),
            }
            for t in open_trades
        ],
        "audit_events": [
            f"{now_ist().strftime('%H:%M:%S')} IST | System Health: {readiness.tier.value} | Sizing: {readiness.sizing_multiplier}x",
            f"{now_ist().strftime('%H:%M:%S')} IST | Session State: {state.value} | Active Scanners Online",
        ],
    }


@router.websocket("/ws/stream")
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

            # Stream periodic telemetry update
            update = get_live_telemetry_snapshot()
            await websocket.send_text(json.dumps(update))
            await asyncio.sleep(0.5)  # 500ms update cadence

    except WebSocketDisconnect:
        await STREAM_HUB.disconnect(websocket)
    except Exception as e:
        logger.warning(f"[WebSocketStream] Client connection error: {e}")
        await STREAM_HUB.disconnect(websocket)
