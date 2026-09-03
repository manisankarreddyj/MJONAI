"""
Module: orchestration/runtime_guard.py
Purpose: SOTA Graceful Process Lifecycle & Teardown Guard for MJONAI.
         Coordinates POSIX/Windows signal handling, WebSocket stream disconnection,
         mutex lock release, and database journal flush during system shutdown.
"""

import atexit
import logging
import os
import signal
import sys
from typing import Optional, Any

from core.runtime_config import LOCK_FILE

logger = logging.getLogger(__name__)

_CLEANUP_CALLED = False


def cleanup(signum: Optional[int] = None, frame: Any = None, should_exit: bool = False) -> None:
    """
    Execute comprehensive multi-tier graceful teardown sequence:
    1. Release process mutex lock file.
    2. Close active WebSocket network streams.
    3. Clear active scheduler cron jobs.
    4. Publish shutdown telemetry and flush logs.
    """
    global _CLEANUP_CALLED
    if _CLEANUP_CALLED:
        return
    _CLEANUP_CALLED = True

    signal_name = f" (Signal {signum})" if signum is not None else ""
    logger.info(f"\n[RuntimeGuard] Initiating graceful shutdown{signal_name}...")

    # 1. Release process mutex lock
    lock_file = LOCK_FILE
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
            logger.info(f"[RuntimeGuard] Removed process lock: {lock_file}")
        except Exception as e:
            logger.warning(f"[RuntimeGuard] Could not remove lock file: {e}")

    # 2. Close active WebSocket connections
    try:
        from data.angelone.websocket import on_close
        on_close()
        logger.info("[RuntimeGuard] WebSocket connection disconnected cleanly.")
    except Exception:
        pass

    # 3. Clear scheduled cron jobs
    try:
        from orchestration.scheduler_setup import clear_all_jobs
        clear_all_jobs()
    except Exception:
        pass

    # 4. Publish shutdown telemetry
    try:
        from communication.events import publish_event
        publish_event("SYSTEM_SHUTDOWN", {"reason": f"Signal {signum}" if signum else "Clean Exit"})
    except Exception:
        pass

    logger.info("✅ MJONAI shutdown complete.")

    if should_exit:
        sys.exit(0)


def register_runtime_guard() -> None:
    """
    Register signal handlers and atexit hook safely on the main execution thread.
    Guards against threading exceptions when called inside sub-threads or test runners.
    """
    # 1. atexit hook runs on any normal interpreter exit
    atexit.register(cleanup)

    # 2. POSIX/Windows OS termination signals
    try:
        def _signal_handler(sig, frame):
            cleanup(signum=sig, frame=frame, should_exit=True)

        signal.signal(signal.SIGINT, _signal_handler)
        signal.signal(signal.SIGTERM, _signal_handler)
        logger.info("[RuntimeGuard] Signal handlers registered for SIGINT and SIGTERM.")
    except (ValueError, AttributeError) as e:
        logger.debug(f"[RuntimeGuard] Signal registration notice (non-main thread): {e}")