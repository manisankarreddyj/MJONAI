"""
Module: communication/events.py
Purpose: SOTA Real-Time Web Event Stream & Ring Buffer for Interactive Web UI Dashboards.
         Emits structured JSON events for Trade Signals, Open Positions, Multi-Agent Debates,
         Risk Alerts, and Market Regime updates over Server-Sent Events (SSE) or WebSockets.
"""

from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import logging
import threading
import time
from typing import Dict, List, Any, Optional, Iterator, Generator

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)

_EVENT_LOCK = threading.RLock()
_MAX_RING_BUFFER_SIZE = 500
_event_sequence = 0
_ring_buffer: deque = deque(maxlen=_MAX_RING_BUFFER_SIZE)
_active_subscribers: List[Any] = []


@dataclass(frozen=True)
class WebEvent:
    """Immutable real-time web event model."""
    event_id: int
    event_type: str  # SIGNAL_EMITTED, TRADE_CLOSED, SL_UPDATED, DEBATE_COMPLETED, EMERGENCY_HALT, MARKET_STATE
    timestamp: str
    payload: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_json(self) -> str:
        return json.dumps(self.to_dict())


_active_listeners: List[Any] = []


def register_event_listener(listener: Any) -> None:
    """Register a callback listener to receive instant pushed WebEvents."""
    with _EVENT_LOCK:
        if listener not in _active_listeners:
            _active_listeners.append(listener)


def unregister_event_listener(listener: Any) -> None:
    """Unregister an event listener."""
    with _EVENT_LOCK:
        if listener in _active_listeners:
            _active_listeners.remove(listener)


def publish_event(event_type: str, payload: Dict[str, Any]) -> WebEvent:
    """
    Publish a structured real-time event to the web streaming ring buffer.
    Notifies registered listeners and fans out to active WebSocket connections.
    """
    global _event_sequence, _ring_buffer
    with _EVENT_LOCK:
        _event_sequence += 1
        event = WebEvent(
            event_id=_event_sequence,
            event_type=str(event_type).upper(),
            timestamp=now_ist().isoformat(),
            payload=payload,
        )
        _ring_buffer.append(event)
        listeners_snapshot = list(_active_listeners)

    # Fan out to listeners outside lock
    for listener in listeners_snapshot:
        try:
            listener(event.to_dict())
        except Exception as e:
            logger.debug(f"[WebEvent] Listener dispatch error: {e}")

    # Auto-bridge to WebSocketHub if available
    try:
        from apps.web.websocket_stream import STREAM_HUB
        import asyncio
        msg = {"type": "EVENT", "event": event.to_dict()}
        # If in an event loop, schedule broadcast task
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(STREAM_HUB.broadcast(msg))
        except RuntimeError:
            pass
    except Exception:
        pass

    logger.debug(f"[WebEvent] Published #{event.event_id} ({event.event_type})")
    return event


def get_recent_events(limit: int = 50, since_id: int = 0) -> List[Dict[str, Any]]:
    """
    Retrieve recent events from the ring buffer for REST polling or SSE replay.
    """
    with _EVENT_LOCK:
        events = [e.to_dict() for e in _ring_buffer if e.event_id > since_id]
        return events[-limit:] if limit > 0 else events


def get_events_since(last_event_id: int) -> List[Dict[str, Any]]:
    """
    Retrieve all events occurred since last_event_id for seamless client reconnection recovery.
    """
    return get_recent_events(limit=0, since_id=last_event_id)


def clear_events_buffer() -> None:
    """Helper for test suites to reset event stream state."""
    global _event_sequence, _ring_buffer
    with _EVENT_LOCK:
        _event_sequence = 0
        _ring_buffer.clear()
