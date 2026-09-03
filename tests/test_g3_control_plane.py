"""
G3 control-plane regression tests (2026-08-24):
  - C3+H10: scanner no longer runs a second (crashing, fail-open) debate layer;
    pipeline Gate 6 remains the single binding AI verdict.
  - C7: two-lane scheduler — a hung heavy job can never stall the fast
    trailing-stop monitor; overrun firings are skipped, not piled up.
  - C8a: websocket messaging is honest — no "alternative/fallback feeds" claims.
  - C8b: re-auth hook fires exactly once, at attempt 3, during stubborn recoveries.
"""

import threading
import time as time_mod
from datetime import timedelta
from pathlib import Path

import pytest

import apps.runtime.orchestration.scheduler_setup as sched_mod
from apps.runtime.orchestration.scheduler_setup import SchedulerEngine, _safe_job
from mjonai.data.angelone import websocket as angel_ws

_REPO_ROOT = Path(__file__).resolve().parents[1]  # repo root (ADR-0008: tests/ at root)


def test_single_binding_debate_layer():
    """C3+H10 pin: the scanner must NOT re-run the adversarial debate
    (main.py passed a bool into conduct_adversarial_debate's list parameter,
    crashing every cycle and failing open). Gate 6 in pipeline owns it."""
    main_src = (_REPO_ROOT / "apps" / "runtime" / "main.py").read_text(encoding="utf-8")
    assert "conduct_adversarial_debate(" not in main_src, (
        "main.py must not CALL a second debate layer (comments may mention it)"
    )
    pipeline_src = (_REPO_ROOT / "mjonai" / "strategy" / "pipeline.py").read_text(encoding="utf-8")
    assert "SUPERVISOR_DEBATE_VETO" in pipeline_src


def test_two_lane_scheduler_isolates_hung_heavy_job():
    """C7: while a heavy job blocks indefinitely, the fast-lane monitor keeps
    firing every tick; heavy overrun firings are skipped (no pile-up)."""
    eng = SchedulerEngine()
    eng._lane_acquire_timeouts["heavy"] = 0.2  # keep the test fast

    gate = threading.Event()
    calls = {"heavy": 0, "fast": 0}

    def heavy_job():
        calls["heavy"] += 1
        gate.wait(timeout=5)

    def fast_job():
        calls["fast"] += 1

    jh = eng.every(1).minutes.do(_safe_job(heavy_job, "heavy_test"))
    jf = eng.every(1).minutes.do(_safe_job(fast_job, "fast_test", lane="fast"))

    base = sched_mod.now_ist()
    jh.next_run = base
    jf.next_run = base
    eng.run_pending(now=base)
    deadline = time_mod.time() + 2.0
    while calls["heavy"] == 0 and time_mod.time() < deadline:
        time_mod.sleep(0.02)
    assert calls["heavy"] == 1, "heavy job should have started"

    # Heavy is stuck holding its lane lock. Fast lane must keep ticking.
    for minute in range(1, 4):
        tick = base + timedelta(minutes=minute)
        jf.next_run = tick
        eng.run_pending(now=tick)
        time_mod.sleep(0.15)
    assert calls["fast"] >= 2, "fast monitor must run while heavy job hangs"

    # Overrun: refiring heavy while stuck must SKIP (still exactly 1 run).
    jh.next_run = base + timedelta(minutes=1)
    eng.run_pending(now=base + timedelta(minutes=1))
    time_mod.sleep(0.2)
    assert calls["heavy"] == 1, "overrun firing of hung heavy job must be skipped"

    gate.set()
    time_mod.sleep(0.3)  # allow the blocked heavy thread to finish + release


def test_websocket_messaging_has_no_fallback_theater():
    """C8a pin: the old messages claimed feeds that do not exist."""
    src = (_REPO_ROOT / "mjonai" / "data" / "angelone" / "websocket.py").read_text(encoding="utf-8")
    assert "alternative feeds" not in src
    assert "fallback feeds active" not in src
    assert "fail closed" in src  # honest statement present


def test_reauth_hook_fires_once_at_attempt_three(monkeypatch):
    """C8b: hook fires exactly once (at attempt 3), tolerates absence, and
    exceptions from the callback cannot kill the reconnect loop."""
    calls = []

    def recorder() -> bool:
        calls.append(1)
        return True

    monkeypatch.setattr(angel_ws, "_reauth_callback", recorder)
    for attempt in range(1, 4):
        angel_ws._maybe_reauth(attempt)
        assert len(calls) == (1 if attempt >= 3 else 0), f"hook state wrong at attempt {attempt}"
    for attempt in range(4, 6):
        angel_ws._maybe_reauth(attempt)
    assert len(calls) == 1, "hook must fire exactly once per recovery loop"

    # No registered hook -> silent no-op.
    monkeypatch.setattr(angel_ws, "_reauth_callback", None)
    angel_ws._maybe_reauth(3)  # must not raise

    # Raising hook -> contained.
    def boom():
        raise RuntimeError("login exploded")

    monkeypatch.setattr(angel_ws, "_reauth_callback", boom)
    angel_ws._maybe_reauth(3)  # must not raise
