"""
Module: orchestration/heartbeat_sentry.py
Purpose: SOTA Autonomous Heartbeat Sentry & Dead-Man's Switch for MJONAI.
         Emits structured JSON heartbeats, monitors process responsiveness,
         and detects silent loop freezes, GIL locks, or thread death.
"""

from dataclasses import dataclass, asdict
from datetime import datetime, timezone
import json
import logging
import os
from pathlib import Path
import time
from typing import Dict, Any, Optional

from mjonai.core.time_utils import now_ist
from apps.runtime.orchestration.market_session_lifecycle import get_current_session_state, MarketSessionState

logger = logging.getLogger(__name__)

DEFAULT_HEARTBEAT_PATH = Path("storage/heartbeat.json")
PROCESS_START_TIME = time.time()


@dataclass(frozen=True)
class HeartbeatPayload:
    """Immutable contract representing an instantaneous system heartbeat."""
    pid: int
    timestamp_ist: str
    uptime_seconds: float
    session_state: str
    is_order_entry_allowed: bool
    cpu_pct: float
    ram_pct: float
    disk_pct: float
    websocket_healthy: bool
    open_positions_count: int
    threads_count: int

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class HeartbeatLivenessReport:
    """Report contract for external watchdog / dead-man's switch verification."""
    is_alive: bool
    age_seconds: float
    pid: Optional[int]
    session_state: Optional[str]
    verdict: str  # "HEALTHY_ACTIVE", "STALE_WARNING", "PROCESS_STALLED_CRITICAL", "NO_HEARTBEAT_FOUND"
    message: str


def emit_heartbeat(
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    websocket_healthy: bool = True,
    open_positions_count: int = 0,
    cpu_pct: float = 0.0,
    ram_pct: float = 0.0,
    disk_pct: float = 0.0,
) -> HeartbeatPayload:
    """
    Generate and atomically write system heartbeat telemetry to disk.
    Guarantees atomic writes via temporary file rename to prevent read contention.
    """
    import threading

    state = get_current_session_state()
    uptime = round(time.time() - PROCESS_START_TIME, 1)
    threads = threading.active_count()

    payload = HeartbeatPayload(
        pid=os.getpid(),
        timestamp_ist=now_ist().isoformat(),
        uptime_seconds=uptime,
        session_state=state.value,
        is_order_entry_allowed=(state == MarketSessionState.REGULAR_MARKET),
        cpu_pct=round(cpu_pct, 1),
        ram_pct=round(ram_pct, 1),
        disk_pct=round(disk_pct, 1),
        websocket_healthy=websocket_healthy,
        open_positions_count=open_positions_count,
        threads_count=threads,
    )

    try:
        heartbeat_path.parent.mkdir(parents=True, exist_ok=True)
        temp_file = heartbeat_path.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(payload.to_dict(), f, indent=2)
        
        # Atomic file replacement
        temp_file.replace(heartbeat_path)
    except Exception as e:
        logger.error(f"[HeartbeatSentry] Failed to write heartbeat file: {e}")

    return payload


def check_heartbeat_liveness(
    heartbeat_path: Path = DEFAULT_HEARTBEAT_PATH,
    max_stale_seconds: float = 90.0,
    now: Optional[datetime] = None,
) -> HeartbeatLivenessReport:
    """
    Inspect heartbeat file to determine if the trading engine process is alive.
    Used by watchdog daemons and monitoring sidecars.
    """
    if not heartbeat_path.exists():
        return HeartbeatLivenessReport(
            is_alive=False,
            age_seconds=-1.0,
            pid=None,
            session_state=None,
            verdict="NO_HEARTBEAT_FOUND",
            message=f"No heartbeat file found at {heartbeat_path}",
        )

    try:
        with open(heartbeat_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        ts_str = data.get("timestamp_ist")
        if not ts_str:
            raise ValueError("Missing timestamp_ist in heartbeat file")

        # Parse ISO timestamp
        hb_time = datetime.fromisoformat(ts_str)
        ref_time = now or now_ist()
        # Remove tzinfo for clean math if needed
        if hb_time.tzinfo and not ref_time.tzinfo:
            hb_time = hb_time.replace(tzinfo=None)
        elif not hb_time.tzinfo and ref_time.tzinfo:
            ref_time = ref_time.replace(tzinfo=None)

        age = max(0.0, (ref_time - hb_time).total_seconds())
        pid = data.get("pid")
        session = data.get("session_state")

        if age > max_stale_seconds:
            return HeartbeatLivenessReport(
                is_alive=False,
                age_seconds=round(age, 1),
                pid=pid,
                session_state=session,
                verdict="PROCESS_STALLED_CRITICAL",
                message=f"Dead-man switch alert: Heartbeat is stale by {age:.1f}s (threshold: {max_stale_seconds}s)",
            )
        elif age > (max_stale_seconds * 0.5):
            return HeartbeatLivenessReport(
                is_alive=True,
                age_seconds=round(age, 1),
                pid=pid,
                session_state=session,
                verdict="STALE_WARNING",
                message=f"Heartbeat delay warning: Age {age:.1f}s approaching stall threshold",
            )
        else:
            return HeartbeatLivenessReport(
                is_alive=True,
                age_seconds=round(age, 1),
                pid=pid,
                session_state=session,
                verdict="HEALTHY_ACTIVE",
                message=f"Heartbeat active: Age {age:.1f}s, PID {pid}, State {session}",
            )

    except Exception as e:
        return HeartbeatLivenessReport(
            is_alive=False,
            age_seconds=-1.0,
            pid=None,
            session_state=None,
            verdict="CORRUPTED_HEARTBEAT",
            message=f"Error reading heartbeat file: {e}",
        )
