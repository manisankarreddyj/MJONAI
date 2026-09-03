"""
Module: orchestration/crash_supervisor.py
Purpose: SOTA Subsystem Crash Watchdog, Jittered Exponential Backoff Supervisor,
         and Critical Fault Telemetry Dispatcher for MJONAI.
"""

from datetime import datetime, timezone, timedelta
import logging
import random
import sys
import threading
import time
import traceback
from typing import Dict, List, Any, Optional, Callable

from core.time_utils import now_ist
from communication.telegram import send_message
from communication.events import publish_event

logger = logging.getLogger(__name__)


class CrashSupervisor:
    """
    Monitors process life-cycles, manages automated restarts with exponential
    backoff and jitter, and limits rapid cascading restart loops.
    """

    def __init__(
        self,
        base_delay_seconds: float = 2.0,
        max_delay_seconds: float = 60.0,
        max_restarts_per_hour: int = 5,
    ):
        self.base_delay = base_delay_seconds
        self.max_delay = max_delay_seconds
        self.max_restarts_per_hour = max_restarts_per_hour
        self.restart_timestamps: List[datetime] = []
        self.consecutive_crashes: int = 0
        self._lock = threading.RLock()

    def compute_backoff_delay(self) -> float:
        """Calculate exponential backoff delay with random jitter."""
        with self._lock:
            # 2^attempts * base_delay, clamped to max_delay
            exp_factor = min(self.max_delay, self.base_delay * (2 ** min(self.consecutive_crashes, 6)))
            # Add +- 20% random jitter
            jitter = random.uniform(0.8, 1.2)
            return float(round(exp_factor * jitter, 2))

    def can_restart(self) -> bool:
        """Check if restart budget within the last rolling hour is exhausted."""
        with self._lock:
            now = now_ist()
            one_hour_ago = now - timedelta(hours=1)
            # Prune older restart timestamps
            self.restart_timestamps = [ts for ts in self.restart_timestamps if ts > one_hour_ago]

            if len(self.restart_timestamps) >= self.max_restarts_per_hour:
                return False
            return True

    def record_crash(self, exc: Exception, subsystem_name: str = "MAIN_ENGINE") -> Dict[str, Any]:
        """Record a crash event, alert communication channels, and compute backoff."""
        with self._lock:
            now = now_ist()
            self.consecutive_crashes += 1
            self.restart_timestamps.append(now)

            can_proceed = self.can_restart()
            delay = self.compute_backoff_delay() if can_proceed else 0.0

            tb = traceback.format_exc()
            logger.critical(
                f"[Crash Supervisor] 🚨 {subsystem_name} crashed (Attempt #{self.consecutive_crashes}). "
                f"Can restart: {can_proceed}. Backoff delay: {delay}s. Error: {exc}"
            )

            # Send high-priority alert safely
            tb_snippet = tb[-500:] if len(tb) > 500 else tb
            try:
                send_message(
                    f"🚨 <b>CRITICAL SYSTEM CRASH</b>\n"
                    f"Subsystem: <code>{subsystem_name}</code>\n"
                    f"Consecutive Crashes: {self.consecutive_crashes}\n"
                    f"Restart Allowed: {can_proceed}\n"
                    f"Backoff Delay: {delay}s\n"
                    f"<pre>{tb_snippet}</pre>"
                )
            except Exception as alert_err:
                logger.warning(f"[Crash Supervisor] Could not send Telegram alert: {alert_err}")

            publish_event("SYSTEM_CRASH", {
                "subsystem": subsystem_name,
                "consecutive_crashes": self.consecutive_crashes,
                "can_restart": can_proceed,
                "backoff_delay": delay,
                "timestamp": now.isoformat(),
            })

            return {
                "can_restart": can_proceed,
                "delay_seconds": delay,
                "consecutive_crashes": self.consecutive_crashes,
                "restarts_last_hour": len(self.restart_timestamps),
            }

    def reset_crash_counter(self) -> None:
        """Reset consecutive crashes counter after stable running interval."""
        with self._lock:
            if self.consecutive_crashes > 0:
                logger.info(f"[Crash Supervisor] Stable running period verified — resetting crash counter from {self.consecutive_crashes} to 0.")
                self.consecutive_crashes = 0
