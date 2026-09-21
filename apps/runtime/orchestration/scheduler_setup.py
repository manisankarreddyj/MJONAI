"""
Module: orchestration/scheduler_setup.py
Purpose: SOTA Master Lifecycle Schedule Coordinator for MJONAI.
         Registers and isolates daily, intraday, EOD, and weekly research jobs
         with automated exception containment, built-in pure Python cron engine,
         and full idempotency across all operating environments.
"""

from datetime import datetime, timedelta, time as dtime
from functools import wraps
import importlib
import logging
import threading
import time
from typing import Callable, Dict, List, Any, Optional, Union

from mjonai.core.time_utils import now_ist

logger = logging.getLogger(__name__)


# ── 1. BUILT-IN PURE PYTHON SCHEDULER ENGINE ─────────────────────────────────

def _parse_hhmm(time_str):
    if not time_str:
        return 0, 0
    parts = str(time_str).strip().split(":")
    try:
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
    except (TypeError, ValueError):
        return 0, 0
    return max(0, min(hour, 23)), max(0, min(minute, 59))


def compute_next_run(job, now=None, after=None):
    """When should this job fire next? Does not run the job."""
    clock = after or now or now_ist()
    hour, minute = _parse_hhmm(job.at_time)

    if job.unit == "minutes":
        if after is None:
            return clock
        return after + timedelta(minutes=max(1, int(job.interval or 1)))

    if job.unit == "weeks" and (job.day_of_week or "").lower() == "sunday":
        candidate = clock.replace(hour=hour, minute=minute, second=0, microsecond=0)
        days_ahead = (6 - clock.weekday()) % 7
        candidate = candidate + timedelta(days=days_ahead)
        if candidate <= clock:
            candidate += timedelta(days=7)
        return candidate

    candidate = clock.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if candidate <= clock:
        candidate += timedelta(days=max(1, int(job.interval or 1)))
    return candidate


class ScheduledJob:
    """Immutable job representation in the scheduler registry."""
    def __init__(self, interval: int = 1, unit: str = "days"):
        self.interval = interval
        self.unit = unit
        self.at_time: Optional[str] = None
        self.day_of_week: Optional[str] = None
        self.job_func: Optional[Callable] = None
        self.job_name: Optional[str] = None
        self.last_run: Optional[datetime] = None
        self.next_run: Optional[datetime] = None
        # C7: execution lane. "fast" = tight-cadence money-protection jobs
        # (trailing-SL monitor); "heavy" = everything else. Lanes serialize
        # internally but never block each other, so a hung scan/report can
        # no longer freeze stop-loss monitoring.
        self.lane: str = "heavy"

    def at(self, time_str: str) -> "ScheduledJob":
        self.at_time = time_str
        return self

    def do(self, job_func: Callable, *args, **kwargs) -> "ScheduledJob":
        self.job_func = job_func
        self.job_name = getattr(job_func, "__name__", str(job_func))
        self.lane = getattr(job_func, "_lane", "heavy")
        self.next_run = compute_next_run(self, now=now_ist())
        return self


class _JobBuilder:
    """Fluent API builder mimicking schedule.every()."""
    def __init__(self, engine: "SchedulerEngine", interval: int = 1):
        self._engine = engine
        self._interval = interval

    @property
    def day(self) -> ScheduledJob:
        job = ScheduledJob(interval=self._interval, unit="days")
        self._engine.jobs.append(job)
        return job

    @property
    def sunday(self) -> ScheduledJob:
        job = ScheduledJob(interval=self._interval, unit="weeks")
        job.day_of_week = "sunday"
        self._engine.jobs.append(job)
        return job

    @property
    def minutes(self) -> ScheduledJob:
        job = ScheduledJob(interval=self._interval, unit="minutes")
        self._engine.jobs.append(job)
        return job


class SchedulerEngine:
    """Pure-Python built-in scheduler engine providing zero-dependency reliability."""
    def __init__(self):
        self.jobs: List[ScheduledJob] = []
        # C7: one serialization lock per lane. Jobs within a lane keep the
        # old sequential semantics; lanes run concurrently in daemon threads
        # so a hung heavy job can never stall the trailing-stop monitor.
        self._lane_locks: Dict[str, threading.Lock] = {
            "fast": threading.Lock(),
            "heavy": threading.Lock(),
        }
        # How long a firing may wait for its lane before being skipped as an
        # overrun. Fast lane must never queue behind anything; heavy lane
        # tolerates brief co-scheduled jobs (e.g. 08:25 reset+connect).
        self._lane_acquire_timeouts = {"fast": 0.5, "heavy": 45.0}

    def every(self, interval: int = 1) -> _JobBuilder:
        return _JobBuilder(self, interval=interval)

    def clear(self) -> None:
        self.jobs.clear()

    def run_pending(self, now=None) -> int:
        clock = now or now_ist()
        fired = 0
        for job in list(self.jobs):
            if job.job_func is None:
                continue
            if job.next_run is None:
                job.next_run = compute_next_run(job, now=clock)
            if clock < job.next_run:
                continue

            lane_lock = self._lane_locks.get(job.lane, self._lane_locks["heavy"])
            acquired = lane_lock.acquire(timeout=self._lane_acquire_timeouts.get(job.lane, 45.0))
            if not acquired:
                # Overrun guard: previous firing of this lane is still
                # running. Skip this firing (no pile-up) and reschedule.
                logger.warning(
                    f"[Scheduler] Lane '{job.lane}' still busy - skipping firing of "
                    f"'{job.job_name}' as overrun (previous invocation has not returned)"
                )
                job.last_run = clock
                job.next_run = compute_next_run(job, now=clock, after=clock)
                continue

            def _execute(j=job, lk=lane_lock, started=time.time()):
                try:
                    j.job_func()
                except Exception as e:
                    logger.error(
                        f"[Scheduler] Uncontained error in '{j.job_name}': {e}",
                        exc_info=True,
                    )
                finally:
                    elapsed = time.time() - started
                    if elapsed > 60.0:
                        logger.warning(
                            f"[Scheduler] Job '{j.job_name}' occupied lane '{j.lane}' for {elapsed:.0f}s"
                        )
                    lk.release()

            threading.Thread(target=_execute, name=f"mjonai-job-{job.job_name}", daemon=True).start()

            job.last_run = clock
            job.next_run = compute_next_run(job, now=clock, after=clock)
            fired += 1
        return fired


_GLOBAL_ENGINE = SchedulerEngine()


def _get_scheduler():
    """Retrieve global scheduler engine."""
    return _GLOBAL_ENGINE


# ── 2. EXCEPTION CONTAINMENT SENTRY ──────────────────────────────────────────

def _safe_job(func: Callable, job_name: str, lane: str = "heavy") -> Callable:
    """
    Wrap scheduled callback in exception containment sentry.
    Guarantees an error in one job never crashes or stops subsequent scheduler jobs.
    Lane (C7): "fast" jobs (money-protection monitors) never queue behind "heavy"
    jobs (scanner/EOD/reports); see SchedulerEngine.run_pending.
    """
    def wrapper(*args, **kwargs):
        t0 = time.time()
        try:
            logger.debug(f"[Scheduler] Executing job: {job_name}")
            result = func(*args, **kwargs)
            duration_ms = int((time.time() - t0) * 1000)
            logger.debug(f"[Scheduler] Completed job: {job_name} ({duration_ms}ms)")
            return result
        except Exception as e:
            duration_ms = int((time.time() - t0) * 1000)
            logger.error(f"[Scheduler] Job '{job_name}' failed after {duration_ms}ms: {e}", exc_info=True)
            return None
    wrapper.__name__ = job_name
    wrapper._lane = lane
    return wrapper


# ── 3. MASTER LIFECYCLE SCHEDULER SETUP ──────────────────────────────────────

def setup_scheduler(
    reset_daily_state: Callable,
    connect_angelone: Callable,
    morning_routine: Callable,
    eod_routine: Callable,
    calculate_forward_returns: Callable,
    generate_daily_report: Callable,
    generate_weekly_report: Callable,
    monitor_trades: Callable,
    scan_and_execute: Callable,
    is_trading_day: Callable,
    weekly_intraday_validation: Optional[Callable] = None,
) -> int:
    """
    Register all trading lifecycle jobs with the global scheduler.
    Ensures idempotent setup by clearing existing jobs first.
    Returns total registered jobs count.
    """
    sch = _get_scheduler()
    sch.clear()

    # ── 1. Pre-Market Jobs (08:25 - 09:00 IST) ───────────────────────
    sch.every().day.at("08:25").do(
        _safe_job(reset_daily_state, "reset_daily_state")
    )

    sch.every().day.at("08:25").do(
        _safe_job(
            lambda: connect_angelone() if is_trading_day() else None,
            "connect_angelone_if_trading_day",
        )
    )

    sch.every().day.at("08:30").do(
        _safe_job(morning_routine, "morning_routine")
    )

    # ── 2. Intraday Fast Cadence Jobs (Market Hours) ──────────────────
    sch.every(1).minutes.do(
        _safe_job(monitor_trades, "monitor_trades_1min", lane="fast")
    )

    sch.every(15).minutes.do(
        _safe_job(scan_and_execute, "scan_and_execute_15min")
    )

    # Minute pipeline Phase 2b (S08 re-enable): native 5m slot. The scanner
    # consumes archived minute bars resampled to 5m; per-strategy
    # `scan_cadences` gating means ONLY S08 (declared ("5m",)) is evaluated
    # here — S13/S17/S18 stay cadence-gated to the 15m slot above.
    sch.every(5).minutes.do(
        _safe_job(lambda: scan_and_execute(timeframe="5m"), "scan_and_execute_5min")
    )

    # ── 3. Post-Market & Research Analytics (15:35 - 17:00 IST) ───────
    sch.every().day.at("15:35").do(
        _safe_job(eod_routine, "eod_routine")
    )

    sch.every().day.at("16:00").do(
        _safe_job(calculate_forward_returns, "calculate_forward_returns")
    )

    sch.every().day.at("16:30").do(
        _safe_job(generate_daily_report, "generate_daily_report")
    )

    # ── 4. Weekend Maintenance (Sunday 10:00 IST) ─────────────────────
    sch.every().sunday.at("10:00").do(
        _safe_job(generate_weekly_report, "generate_weekly_report")
    )

    # Dev/ops loop Phase 1: guarded weekly intraday walk-forward on the live
    # minute archive (fail-closed readiness gate — the heavy research CLI is
    # never spawned while the archive is empty/thin; see validation_schedule.py).
    if weekly_intraday_validation is not None:
        sch.every().sunday.at("10:30").do(
            _safe_job(weekly_intraday_validation, "weekly_intraday_validation")
        )

    jobs_count = len(sch.jobs)
    logger.info(f"✅ Master Scheduler active ({jobs_count} jobs registered):")
    logger.info("  • 08:25 IST — Daily state reset + Angel One re-auth")
    logger.info("  • 08:30 IST — Morning macro & RRG sector briefing")
    logger.info("  • Every 1 min — Active trade trailing SL & MTM monitor")
    logger.info("  • Every 5 min — Native 5m scanner & AI debate (S08 all-day intraday)")
    logger.info("  • Every 15 min — Multi-strategy scanner & AI debate")
    logger.info("  • 15:35 IST — EOD performance scorecard")
    logger.info("  • 16:00 IST — Machine learning forward returns computation")
    logger.info("  • 16:30 IST — Daily research report generation")
    logger.info("  • Sunday 10:00 IST — Weekly Alphalens factor analytics")
    logger.info("  • Sunday 10:30 IST — Weekly intraday walk-forward validation (guarded)")

    return jobs_count


def get_scheduled_jobs_summary() -> List[Dict[str, Any]]:
    """Retrieve summary of all active scheduled jobs for telemetry."""
    sch = _get_scheduler()
    summary: List[Dict[str, Any]] = []
    for j in sch.jobs:
        name = j.job_name or str(getattr(j.job_func, "__name__", j.job_func))
        summary.append({
            "job": name,
            "interval": j.interval,
            "unit": j.unit,
            "at_time": j.at_time,
            "day_of_week": j.day_of_week,
            "next_run": j.next_run.isoformat() if j.next_run else None,
            "last_run": j.last_run.isoformat() if j.last_run else None,
        })
    return summary


def clear_all_jobs() -> None:
    """Clear all scheduled jobs from memory."""
    sch = _get_scheduler()
    sch.clear()
    logger.info("[Scheduler] All scheduled jobs cleared from memory.")