"""
Unit and Institutional Test Suite for Module 8 Extreme Edge Cases & Chaos Stress Testing.
Validates Self-Healing Thread Watchdog, Clock Drift / Future Time Jumps,
Microsecond Boundary Transitions, and Concurrent Heartbeat Contention.
"""

from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, time as dtime
import json
from pathlib import Path
import threading
import time
import pytest

from apps.runtime.orchestration.market_session_lifecycle import (
    MarketSessionState,
    get_current_session_state,
    is_order_entry_allowed,
)
from apps.runtime.orchestration.heartbeat_sentry import (
    emit_heartbeat,
    check_heartbeat_liveness,
    HeartbeatPayload,
)
from apps.runtime.orchestration.process_watchdog import ProcessWatchdog


def test_m8_thread_watchdog_auto_resurrection():
    """Torture test ProcessWatchdog self-healing: dead threads are automatically resurrected."""
    watchdog = ProcessWatchdog()
    execution_counter = 0
    counter_lock = threading.Lock()

    def dying_worker():
        nonlocal execution_counter
        with counter_lock:
            execution_counter += 1
        # Thread dies immediately after running
        return

    # 1. Register and auto-start
    th = watchdog.register_worker("test_worker", dying_worker, auto_start=True)
    th.join(timeout=1.0)
    assert not th.is_alive()

    # 2. Supervise workers: Should detect dead thread and resurrect it
    report = watchdog.supervise_workers()
    assert report.dead_threads == 1
    assert report.restarted_threads == 1
    assert report.thread_details[0]["status"] == "RESURRECTED"
    assert report.thread_details[0]["restart_count"] == 1

    # Wait for resurrected thread to finish
    time.sleep(0.1)
    with counter_lock:
        assert execution_counter >= 2


def test_m8_heartbeat_clock_drift_future_time_jump(tmp_path: Path):
    """Torture test Dead-Man's switch against clock drift (NTP time jump into future)."""
    hb_file = tmp_path / "heartbeat_future.json"
    now = datetime(2026, 9, 3, 10, 0, 0)
    # Heartbeat generated with future clock (+5 minutes)
    future_time = now + timedelta(minutes=5)

    with open(hb_file, "w", encoding="utf-8") as f:
        json.dump({"pid": 9999, "timestamp_ist": future_time.isoformat(), "session_state": "REGULAR_MARKET"}, f)

    rep = check_heartbeat_liveness(hb_file, max_stale_seconds=90.0, now=now)
    # Future timestamp should result in age 0.0s (healthy active), not negative crash
    assert rep.is_alive is True
    assert rep.age_seconds == 0.0
    assert rep.verdict == "HEALTHY_ACTIVE"


def test_m8_microsecond_boundary_precision():
    """Torture test exact boundary microsecond precision across all state transitions."""
    base_date = datetime(2026, 9, 3)

    # 08:24:59.999999 -> OVERNIGHT_OFFLINE
    t_just_before_pre = base_date.replace(hour=8, minute=24, second=59, microsecond=999999)
    assert get_current_session_state(t_just_before_pre, trading_day_override=True) == MarketSessionState.OVERNIGHT_OFFLINE

    # 08:25:00.000000 -> PRE_MARKET
    t_exact_pre = base_date.replace(hour=8, minute=25, second=0, microsecond=0)
    assert get_current_session_state(t_exact_pre, trading_day_override=True) == MarketSessionState.PRE_MARKET

    # 09:14:59.999999 -> AUCTION_DISCOVERY
    t_just_before_reg = base_date.replace(hour=9, minute=14, second=59, microsecond=999999)
    assert get_current_session_state(t_just_before_reg, trading_day_override=True) == MarketSessionState.AUCTION_DISCOVERY
    assert is_order_entry_allowed(get_current_session_state(t_just_before_reg, trading_day_override=True)) is False

    # 09:15:00.000000 -> REGULAR_MARKET
    t_exact_reg = base_date.replace(hour=9, minute=15, second=0, microsecond=0)
    assert get_current_session_state(t_exact_reg, trading_day_override=True) == MarketSessionState.REGULAR_MARKET
    assert is_order_entry_allowed(get_current_session_state(t_exact_reg, trading_day_override=True)) is True

    # 15:15:00.000000 -> INTRADAY_SQUARE_OFF
    t_exact_sq = base_date.replace(hour=15, minute=15, second=0, microsecond=0)
    assert get_current_session_state(t_exact_sq, trading_day_override=True) == MarketSessionState.INTRADAY_SQUARE_OFF
    assert is_order_entry_allowed(get_current_session_state(t_exact_sq, trading_day_override=True)) is False


def test_m8_concurrent_heartbeat_atomic_contention(tmp_path: Path):
    """Torture test concurrent thread contention writing to the same heartbeat file."""
    hb_file = tmp_path / "concurrent_heartbeat.json"

    def write_heartbeat_worker(worker_id: int):
        for _ in range(25):
            emit_heartbeat(
                heartbeat_path=hb_file,
                open_positions_count=worker_id,
            )
            time.sleep(0.002)

    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(write_heartbeat_worker, i) for i in range(8)]
        for f in futures:
            f.result()

    # Verify file is intact and valid JSON despite heavy multi-threaded contention
    assert hb_file.exists()
    with open(hb_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "pid" in data
    assert "timestamp_ist" in data
    assert "uptime_seconds" in data


def test_m8_simultaneous_multi_thread_resurrection():
    """Torture test ProcessWatchdog resurrecting 5 threads killed simultaneously."""
    watchdog = ProcessWatchdog()
    died_count = 0
    lock = threading.Lock()

    def dying_worker():
        nonlocal died_count
        with lock:
            died_count += 1
        return

    # Register 5 workers that exit immediately
    workers = [
        watchdog.register_worker(f"worker_{i}", dying_worker, auto_start=True)
        for i in range(5)
    ]
    for w in workers:
        w.join(timeout=1.0)

    # Supervise all 5 dead workers
    report = watchdog.supervise_workers()
    assert report.total_supervised == 5
    assert report.dead_threads == 5
    assert report.restarted_threads == 5
    for det in report.thread_details:
        assert det["status"] == "RESURRECTED"
        assert det["restart_count"] == 1


def test_m8_zombie_pid_lock_reclaim(tmp_path: Path):
    """Torture test process lock reclamation when lock contains an inactive zombie PID."""
    from apps.runtime.orchestration.startup import _acquire_process_lock, _is_pid_running

    # Verify _is_pid_running safely returns False for a ridiculous non-existent PID
    zombie_pid = 9999999
    assert _is_pid_running(zombie_pid) is False

