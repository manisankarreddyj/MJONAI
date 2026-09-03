"""
Module: orchestration/websocket_supervisor.py
Purpose: SOTA Automated Feed Liveness Sentry & Reconnect Supervisor for MJONAI.
         Monitors live tick stream staleness, orchestrates reconnect loops with rate-limiting,
         tracks consecutive failures, and engages REST snapshot polling fallback if required.
"""

from datetime import datetime, timezone
import logging
import threading
from typing import Dict, List, Any, Optional

from mjonai.core.time_utils import now_ist
from mjonai.communication.telegram import send_message
from mjonai.communication.events import publish_event
from mjonai.core.runtime_config import WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS

logger = logging.getLogger(__name__)

_SUPERVISOR_LOCK = threading.RLock()
_last_stale_alert_time: Optional[datetime] = None
_last_reconnect_attempt_time: Optional[datetime] = None
_recovery_in_progress: bool = False
_consecutive_reconnect_attempts: int = 0
_rest_fallback_active: bool = False
_MAX_CONSECUTIVE_RECONNECTS = 3
_MIN_RECONNECT_INTERVAL_SECONDS = 30.0


def handle_websocket_health(ws_healthy: bool) -> Dict[str, Any]:
    """
    Supervise WebSocket feed health.
    If feed is stale, rate-limits alerts, triggers automatic re-authentication,
    and falls back to REST polling if consecutive reconnects exceed threshold.
    """
    global _last_stale_alert_time, _last_reconnect_attempt_time, _recovery_in_progress, _consecutive_reconnect_attempts, _rest_fallback_active

    with _SUPERVISOR_LOCK:
        # 1. Healthy state restoration
        if ws_healthy:
            was_recovering = _recovery_in_progress or _consecutive_reconnect_attempts > 0
            _recovery_in_progress = False
            _consecutive_reconnect_attempts = 0
            _rest_fallback_active = False

            if was_recovering:
                logger.info("[WebSocket Supervisor] Feed fully restored and healthy ✅")
                publish_event("WEBSOCKET_HEALTHY", {"status": "RESTORED", "timestamp": now_ist().isoformat()})

            return {"healthy": True, "recovery_in_progress": False, "rest_fallback": False}

        # 2. Feed is stale / disconnected
        _consecutive_reconnect_attempts += 1
        now = now_ist()

        should_alert = (
            _last_stale_alert_time is None or
            (now - _last_stale_alert_time).total_seconds() >= WEBSOCKET_STALE_ALERT_INTERVAL_SECONDS
        )

        if should_alert:
            _last_stale_alert_time = now
            logger.warning(
                f"[WebSocket Supervisor] Feed stale (attempt #{_consecutive_reconnect_attempts}). "
                "Triggering automated re-authentication..."
            )

            fallback_note = "\n⚠️ <i>Engaged REST polling fallback for position monitoring.</i>" if _consecutive_reconnect_attempts >= _MAX_CONSECUTIVE_RECONNECTS else ""

            send_message(
                f"⚠️ <b>MJONAI FEED ALERT</b>\n"
                f"No live ticks for 2+ minutes (Attempt #{_consecutive_reconnect_attempts}).\n"
                f"Attempting automatic WebSocket recovery...{fallback_note}"
            )
            publish_event("WEBSOCKET_STALE", {
                "consecutive_attempts": _consecutive_reconnect_attempts,
                "timestamp": now.isoformat(),
            })

        # 3. Trip REST fallback if threshold breached
        if _consecutive_reconnect_attempts >= _MAX_CONSECUTIVE_RECONNECTS:
            _rest_fallback_active = True
            logger.critical(
                f"[WebSocket Supervisor] {_consecutive_reconnect_attempts} consecutive reconnects failed. "
                "Active positions protected via REST polling fallback."
            )

        if _recovery_in_progress:
            return {
                "healthy": False,
                "recovery_in_progress": True,
                "consecutive_attempts": _consecutive_reconnect_attempts,
                "rest_fallback": _rest_fallback_active,
            }

        # Rate-limit physical reconnect attempts to prevent 429 connection limit storms
        if _last_reconnect_attempt_time is not None:
            elapsed = (now - _last_reconnect_attempt_time).total_seconds()
            if elapsed < _MIN_RECONNECT_INTERVAL_SECONDS:
                logger.debug(f"[WebSocket Supervisor] Reconnect throttled ({elapsed:.1f}s < {_MIN_RECONNECT_INTERVAL_SECONDS}s)")
                return {
                    "healthy": False,
                    "recovery_in_progress": False,
                    "consecutive_attempts": _consecutive_reconnect_attempts,
                    "rest_fallback": _rest_fallback_active,
                }

        # 4. Trigger WebSocket restart
        _recovery_in_progress = True
        _last_reconnect_attempt_time = now
        logger.warning("[WebSocket Supervisor] Reconnecting Angel One SmartStream...")

        try:
            from mjonai.data.angelone.websocket import restart_websocket
            restart_websocket()
        except Exception as e:
            logger.error(f"[WebSocket Supervisor] restart_websocket error: {e}")
        finally:
            _recovery_in_progress = False

        return {
            "healthy": False,
            "recovery_in_progress": False,
            "consecutive_attempts": _consecutive_reconnect_attempts,
            "rest_fallback": _rest_fallback_active,
        }


def get_supervisor_state() -> Dict[str, Any]:
    """Retrieve telemetry state of the WebSocket supervisor."""
    with _SUPERVISOR_LOCK:
        return {
            "recovery_in_progress": _recovery_in_progress,
            "consecutive_attempts": _consecutive_reconnect_attempts,
            "rest_fallback_active": _rest_fallback_active,
            "last_alert_time": _last_stale_alert_time.isoformat() if _last_stale_alert_time else None,
        }


def reset_supervisor_state() -> None:
    """Reset supervisor state (useful for test fixtures)."""
    global _last_stale_alert_time, _recovery_in_progress, _consecutive_reconnect_attempts, _rest_fallback_active
    with _SUPERVISOR_LOCK:
        _last_stale_alert_time = None
        _recovery_in_progress = False
        _consecutive_reconnect_attempts = 0
        _rest_fallback_active = False