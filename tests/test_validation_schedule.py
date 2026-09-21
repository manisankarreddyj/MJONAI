"""Regression tests: guarded weekly intraday validation (dev/ops loop Phase 1).

Pins the fail-closed semantics of apps/runtime/orchestration/validation_schedule.py:
  - an empty/thin 1m archive DEFERS the heavy research CLI (never spawned);
  - a ready archive spawns the CLI and surfaces the durable verdict;
  - stdout/exit-code summarizing is pure and verbatim-faithful to the research
    CLI's print contract (ROBUST / OVERFIT / NO_WINDOWS).
All OFFLINE: temp parquet roots + stubbed subprocess seam."""

from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest

from mjonai.core.enums import AdjustmentMode, Provider
from mjonai.data.minute_archive import MinuteBarArchive, _make_instrument
from mjonai.research.data.models import Candle, HistoricalData
from mjonai.research.data.timeframe import TimeFrame
from mjonai.storage.models import StorageKey

from apps.runtime.orchestration import validation_schedule as vs
from apps.runtime.orchestration.validation_schedule import (
    intraday_validation_readiness,
    run_weekly_intraday_validation,
    summarize_walk_forward_run,
)

# Two stocks with >= 500 resampled 5m bars spanning > 20 days lets the
# readiness gate pass with the DEFAULT probe list (RELIANCE + HDFCBANK).
PROBE = ["RELIANCE", "HDFCBANK"]


def _seed_archive(root, symbols, days=520, minutes_per_day=5):
    """Persist dense synthetic 1m RAW history through the archive's own
    ParquetStore identity (ANGEL/RAW/NSE/SYMBOL/1m_raw.parquet)."""
    archive = MinuteBarArchive(root=str(root))
    base = datetime(2026, 1, 5, 9, 15, 0)
    for sym in symbols:
        candles = []
        for d in range(days):
            for m in range(minutes_per_day):
                ts = base + timedelta(days=d, minutes=m)
                price = 1000.0 + d * 0.5 + m
                candles.append(
                    Candle(
                        timestamp=ts,
                        open=price,
                        high=price + 1.0,
                        low=price - 1.0,
                        close=price + 0.2,
                        volume=100.0,
                    )
                )
        archive._store.save(
            StorageKey(
                provider=Provider.ANGEL,
                instrument=_make_instrument(sym),
                timeframe=TimeFrame.MIN_1,
                adjustment_mode=AdjustmentMode.RAW,
            ),
            HistoricalData(
                instrument=_make_instrument(sym),
                timeframe=TimeFrame.MIN_1,
                candles=candles,
            ),
        )
    return archive


# ── Readiness gate ───────────────────────────────────────────────────────────


def test_readiness_false_when_archive_empty(tmp_path):
    archive = MinuteBarArchive(root=str(tmp_path))
    ready, reason = intraday_validation_readiness(
        archive=archive, probe_symbols=PROBE
    )
    assert ready is False
    assert "insufficient" in reason


def test_readiness_true_when_two_symbols_have_history(tmp_path):
    archive = _seed_archive(tmp_path, PROBE)
    ready, reason = intraday_validation_readiness(
        archive=archive, probe_symbols=PROBE
    )
    assert ready is True
    assert "RELIANCE" in reason and "HDFCBANK" in reason


def test_readiness_false_when_below_min_ready_symbols(tmp_path):
    archive = _seed_archive(tmp_path, ["RELIANCE"])
    ready, _ = intraday_validation_readiness(
        archive=archive, probe_symbols=PROBE, min_ready_symbols=2
    )
    assert ready is False


def test_readiness_false_when_span_too_short(tmp_path):
    archive = _seed_archive(tmp_path, PROBE, days=5)
    ready, _ = intraday_validation_readiness(
        archive=archive,
        probe_symbols=PROBE,
        min_resampled_bars=5,
        min_span_days=20,
    )
    assert ready is False


def test_readiness_true_when_min_spans_met(tmp_path):
    archive = _seed_archive(tmp_path, PROBE, days=30)
    ready, _ = intraday_validation_readiness(
        archive=archive,
        probe_symbols=PROBE,
        min_resampled_bars=25,
        min_span_days=20,
    )
    assert ready is True


# ── Verdict summarizer (verbatim to the research CLI's print contract) ───────


def test_summarize_robust_run():
    stdout = (
        "WALK-FORWARD SUMMARY: 12 Windows Evaluated across 5 Stocks\n"
        "Avg In-Sample Return : 18.20%\n"
        "Avg Out-of-Sample Ret: 9.40%\n"
        "Overall WFE: 62.0% | IS 15.10% | OOS 8.20% | stability 0.41 | pooled OOS trades 84\n"
        "Canonical WFE Gate (>=50% AND OOS>0 AND pooled OOS trades >= 30): ROBUST\n"
    )
    summary = summarize_walk_forward_run(0, stdout=stdout, stderr="")
    assert summary["verdict"] == "ROBUST"
    assert summary["windows"] == 12
    assert summary["pooled_oos_trades"] == 84
    assert summary["wfe_pct"] == pytest.approx(62.0)


def test_summarize_overfit_run():
    stdout = (
        "WALK-FORWARD SUMMARY: 4 Windows Evaluated across 5 Stocks\n"
        "Overall WFE: 12.0% | IS 9.00% | OOS -3.10% | stability 0.20 | pooled OOS trades 31\n"
        "Canonical WFE Gate (>=50% AND OOS>0 AND pooled OOS trades >= 30): NOT ROBUST (WFE below 50)\n"
    )
    summary = summarize_walk_forward_run(1, stdout=stdout, stderr="")
    assert summary["verdict"] == "OVERFIT"
    assert "NOT ROBUST" in summary["gate"]
    assert summary["pooled_oos_trades"] == 31


def test_summarize_no_windows_exit_two():
    stderr = "FATAL: no walk-forward windows completed - cannot validate. (train 1y + val 1y + 7d embargo exceed available history)"
    summary = summarize_walk_forward_run(2, stdout="", stderr=stderr)
    assert summary["verdict"] == "NO_WINDOWS"
    assert "FATAL" in summary["note"]


def test_summarize_no_output_is_never_certified():
    summary = summarize_walk_forward_run(3, stdout="", stderr="")
    assert summary["verdict"] in ("ERROR", "NO_WINDOWS")


# ── Scheduled job orchestration ──────────────────────────────────────────────


def test_job_defers_without_spawning_cli_when_archive_thin(monkeypatch, tmp_path):
    messages = []
    archive = MinuteBarArchive(root=str(tmp_path))

    def bomb(*args, **kwargs):
        raise AssertionError("the research CLI must not be spawned on a thin archive")

    monkeypatch.setattr(vs, "_launch_walk_forward", bomb)

    result = run_weekly_intraday_validation(notifier=messages.append, archive=archive)
    assert result["ran"] is False
    assert messages, "a deferral note must be notified"
    assert "deferred" in messages[0].lower()


def test_job_runs_cli_when_ready_and_reports_verdict(monkeypatch, tmp_path):
    archive = _seed_archive(tmp_path, PROBE)
    stdout = (
        "WALK-FORWARD SUMMARY: 3 Windows Evaluated across 5 Stocks\n"
        "Overall WFE: 20.0% | IS 8.00% | OOS -2.00% | stability 0.15 | pooled OOS trades 33\n"
        "Canonical WFE Gate (>=50% AND OOS>0 AND pooled OOS trades >= 30): NOT ROBUST (WFE below 50)\n"
    )
    stub = SimpleNamespace(returncode=1, stdout=stdout, stderr="")
    monkeypatch.setattr(vs, "_launch_walk_forward", lambda cmd, timeout_s: stub)

    messages = []
    result = run_weekly_intraday_validation(notifier=messages.append, archive=archive)
    assert result["ran"] is True
    assert result["verdict"] == "OVERFIT"
    assert result["windows"] == 3
    assert messages and "OVERFIT" in messages[0]


def test_job_reports_launch_error_fail_open(monkeypatch, tmp_path):
    archive = _seed_archive(tmp_path, PROBE)

    def boom(cmd, timeout_s):
        raise RuntimeError("simulated CLI crash")

    monkeypatch.setattr(vs, "_launch_walk_forward", boom)
    result = run_weekly_intraday_validation(
        notifier=lambda msg: None, archive=archive
    )
    assert result["ran"] is True
    assert result["verdict"] == "ERROR"
    assert "simulated CLI crash" in result["note"]