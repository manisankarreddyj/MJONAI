"""
Module: orchestration/process_watchdog.py
Purpose: SOTA Self-Healing Thread Watchdog & Worker Supervisor for MJONAI.
         Tracks background threads, detects thread crashes/terminations,
         and orchestrates automated self-healing thread resurrection.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime
import logging
import threading
import time
from typing import Dict, Any, List, Optional, Callable

from mjonai.core.time_utils import now_ist
from mjonai.communication.telegram import send_message

logger = logging.getLogger(__name__)


@dataclass
class SupervisedThreadEntry:
    """Internal registry entry for a supervised worker thread."""
    name: str
    target_func: Callable
    is_daemon: bool
    restart_count: int = 0
    last_restart_time: Optional[datetime] = None
    thread_obj: Optional[threading.Thread] = None


@dataclass(frozen=True)
class ThreadSupervisionReport:
    """Telemetry report for all active and supervised threads."""
    total_supervised: int
    healthy_threads: int
    dead_threads: int
    restarted_threads: int
    thread_details: List[Dict[str, Any]]

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class ProcessWatchdog:
    """Thread-safe watchdog supervisor for mission-critical background workers."""
    def __init__(self):
        self._lock = threading.RLock()
        self._registry: Dict[str, SupervisedThreadEntry] = {}

    def register_worker(
        self,
        name: str,
        target: Callable,
        is_daemon: bool = True,
        auto_start: bool = True,
    ) -> threading.Thread:
        """Register a vital worker thread and optionally start it immediately."""
        with self._lock:
            th = threading.Thread(target=target, name=name, daemon=is_daemon)
            entry = SupervisedThreadEntry(
                name=name,
                target_func=target,
                is_daemon=is_daemon,
                thread_obj=th,
            )
            self._registry[name] = entry

            if auto_start:
                th.start()
                logger.info(f"[ProcessWatchdog] Started worker thread: '{name}' (Daemon={is_daemon})")

            return th

    def supervise_workers(self) -> ThreadSupervisionReport:
        """
        Inspect all registered threads.
        If a thread is dead, resurrects it by creating and starting a new thread instance.
        """
        with self._lock:
            healthy = 0
            dead = 0
            restarted = 0
            details: List[Dict[str, Any]] = []

            for name, entry in self._registry.items():
                th = entry.thread_obj
                is_alive = th is not None and th.is_alive()

                if is_alive:
                    healthy += 1
                    details.append({
                        "name": name,
                        "status": "ALIVE",
                        "restart_count": entry.restart_count,
                        "last_restart": entry.last_restart_time.isoformat() if entry.last_restart_time else None,
                    })
                else:
                    dead += 1
                    logger.warning(f"[ProcessWatchdog] ⚠️ Worker thread '{name}' died! Resurrecting worker...")
                    # Resurrect worker
                    try:
                        new_th = threading.Thread(
                            target=entry.target_func,
                            name=f"{name}-resurrected-{entry.restart_count + 1}",
                            daemon=entry.is_daemon,
                        )
                        new_th.start()
                        entry.thread_obj = new_th
                        entry.restart_count += 1
                        entry.last_restart_time = now_ist()
                        restarted += 1

                        details.append({
                            "name": name,
                            "status": "RESURRECTED",
                            "restart_count": entry.restart_count,
                            "last_restart": entry.last_restart_time.isoformat(),
                        })
                        logger.info(f"[ProcessWatchdog] ✅ Worker '{name}' successfully resurrected (Attempt {entry.restart_count}).")
                    except Exception as e:
                        logger.error(f"[ProcessWatchdog] ❌ Failed to resurrect worker '{name}': {e}", exc_info=True)
                        details.append({
                            "name": name,
                            "status": "RESURRECTION_FAILED",
                            "restart_count": entry.restart_count,
                            "error": str(e),
                        })

            return ThreadSupervisionReport(
                total_supervised=len(self._registry),
                healthy_threads=healthy,
                dead_threads=dead,
                restarted_threads=restarted,
                thread_details=details,
            )


GLOBAL_WATCHDOG = ProcessWatchdog()
