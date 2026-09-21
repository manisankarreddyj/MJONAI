"""
Module: apps/runtime/orchestration/validation_schedule.py

Purpose: Dev/ops loop Phase 1 -- guarded weekly intraday walk-forward validation.

The runtime engine already automates the trading side (scheduler_setup.py). This
module automates the validation side: every Sunday at 10:30 IST the scheduler
runs the real research walk-forward CLI (apps/research/run_walk_forward.py) on
the live-captured minute archive for the flagship intraday strategy, and
notifies the operator with the durable verdict.

Honesty contract (mirrors the research discipline, MJONAI_DOCS.md §8):
  1. FAIL-CLOSED READINESS GATE -- the heavy research CLI is never spawned while
     the archive is empty/thin. `intraday_validation_readiness` probes the
     ANGEL/RAW 1m archive and requires a minimum number of probe symbols each
     holding a minimum number of resampled bars spanning a minimum number of
     days. Below that the job defers (Telegram note) -- a fabricated verdict is
     impossible by construction.
  2. THE CLI DECIDES -- once spawned, the canonical WFE gate (>=50% AND OOS>0
     AND pooled OOS trades >= 30; fail-closed zero-window run exits 2) is the
     source of truth; this module only summarizes stdout + exit code.
  3. EVIDENCE -- the CLI already persists versioned verdict artifacts via
     mjonai/research/evidence.record_evidence; this module never writes its own.
  4. TELEMETRY NEVER A TRADING GATE -- a broken validation notification cannot
     touch trading; every notification is best-effort and contained.
"""

from __future__ import annotations

import logging
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence

from mjonai.communication.telegram import send_message
from mjonai.data.minute_archive import MinuteBarArchive, _DEFAULT_ARCHIVE

logger = logging.getLogger(__name__)

# A probe symbol counts as "ready" when the archive holds at least
# MIN_RESAMPLED_BARS resampled bars covering at least MIN_SPAN_DAYS calendar
# days at the scan cadence, observed for at least MIN_READY_SYMBOLS probe
# symbols. Two ready symbols is the practical floor for a pooled cross-symbol
# validation to ever be meaningful; the WFE gate still owns the final
# "is this valuable?" decision.
DEFAULT_PROBE_SYMBOLS: Sequence[str] = (
    "RELIANCE",
    "HDFCBANK",
    "INFY",
    "TCS",
    "ICICIBANK",
    "SBIN",
    "AXISBANK",
    "LT",
    "ITC",
    "TATAMOTORS",
)
MIN_READY_SYMBOLS = 2
MIN_RESAMPLED_BARS = 500
MIN_SPAN_DAYS = 20

DEFAULT_STRATEGY = "S08_IntradayAllDay"
DEFAULT_TIMEFRAME = "5m"
WALK_FORWARD_TIMEOUT_S = 3600

_REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CLI_PATH = _REPO_ROOT / "apps" / "research" / "run_walk_forward.py"


def intraday_validation_readiness(
    *,
    archive: Optional[MinuteBarArchive] = None,
    cadence: str = DEFAULT_TIMEFRAME,
    probe_symbols: Sequence[str] = DEFAULT_PROBE_SYMBOLS,
    min_ready_symbols: int = MIN_READY_SYMBOLS,
    min_resampled_bars: int = MIN_RESAMPLED_BARS,
    min_span_days: int = MIN_SPAN_DAYS,
) -> tuple[bool, str]:
    """Fail-closed readiness probe for a weekly intraday walk-forward.

    Never throws: an archive that cannot be probed counts as not ready (this is
    research telemetry, not a trading gate). Returns (ready, reason).
    """
    use_archive = archive if archive is not None else _DEFAULT_ARCHIVE
    ready_symbols: List[str] = []
    for symbol in probe_symbols:
        try:
            df = use_archive.load_cadence(
                symbol, cadence=cadence, min_bars=min_resampled_bars
            )
        except Exception:
            continue
        if df is None or df.empty:
            continue
        try:
            span_days = float((df.index[-1] - df.index[0]).total_seconds()) / 86400.0
        except Exception:
            continue
        if span_days < min_span_days:
            continue
        ready_symbols.append(symbol)

    if len(ready_symbols) >= min_ready_symbols:
        return True, (
            f"{len(ready_symbols)} symbols have an adequate archive "
            f"(>= {min_resampled_bars} resampled {cadence} bars over "
            f">= {min_span_days} days): {', '.join(ready_symbols)}"
        )
    return False, (
        f"minute archive insufficient for intraday validation "
        f"({len(ready_symbols)}/{min_ready_symbols} probe symbols hold "
        f">= {min_resampled_bars} resampled {cadence} bars over "
        f">= {min_span_days} days); the engine must keep running during "
        f"market hours to accrue more 1m bars"
    )


def summarize_walk_forward_run(
    exit_code: int,
    stdout: str = "",
    stderr: str = "",
) -> Dict[str, Any]:
    """Extract the durable verdict from the research CLI output (pure function).

    Verdict vocabulary mirrors the evidence store:
      ROBUST / OVERFIT / NO_WINDOWS / ERROR.
    """
    out = stdout or ""
    summary: Dict[str, Any] = {"verdict": "ERROR"}

    windows = re.search(r"SUMMARY:\s*(\d+)\s+Windows", out)
    oos = re.search(r"pooled OOS trades\s+(\d+)", out)
    wfe = re.search(r"Overall WFE:\s*([-\d.]+)%", out)
    avg_oos = re.search(r"Avg Out-of-Sample Ret:\s*([-\d.]+)%", out)
    gate = re.search(r"Canonical WFE Gate[^\n]*:\s*(.+)", out)

    if windows:
        summary["windows"] = int(windows.group(1))
    if oos:
        summary["pooled_oos_trades"] = int(oos.group(1))
    if wfe:
        summary["wfe_pct"] = float(wfe.group(1))
    if avg_oos:
        summary["avg_oos_pct"] = float(avg_oos.group(1))
    if gate:
        summary["gate"] = gate.group(1).strip()

    # Zero-window runs are the honest fail-closed "cannot validate yet" state:
    # the CLI exits 2 and records a NO_WINDOWS evidence artifact. A missing
    # summary line is treated the same way -- never certified, never guessed.
    if exit_code == 2 or windows is None:
        summary["verdict"] = "NO_WINDOWS"
        if stderr:
            fatal = re.search(r"FATAL[^\n]*", stderr)
            if fatal:
                summary["note"] = fatal.group(0).strip()
            else:
                summary["note"] = "no completed walk-forward windows (see CLI stderr)"
        else:
            summary["note"] = "no completed walk-forward windows (train + val + embargo exceed archived history)"
    elif gate and gate.group(1).strip().startswith("ROBUST"):
        summary["verdict"] = "ROBUST"
    else:
        summary["verdict"] = "OVERFIT"

    return summary


def _format_weekly_message(strategy: str, timeframe: str, summary: Dict[str, Any]) -> str:
    """Human-readable Telegram summary of the weekly validation verdict."""
    lines = [
        f"Weekly intraday validation -- {strategy} @ {timeframe}",
        f"verdict: <b>{summary.get('verdict')}</b>",
    ]
    if "windows" in summary:
        lines.append(
            f"windows={summary.get('windows')} | pooled OOS trades="
            f"{summary.get('pooled_oos_trades', 'n/a')} | WFE="
            f"{summary.get('wfe_pct', 'n/a')}% | avg OOS="
            f"{summary.get('avg_oos_pct', 'n/a')}%"
        )
    if summary.get("gate"):
        lines.append(f"gate: {summary['gate']}")
    if summary.get("note"):
        lines.append(summary["note"])
    if summary.get("verdict") == "NO_WINDOWS":
        lines.append("keep the engine running during market hours so the 1m archive grows")
    lines.append("(persisted: storage/research_evidence/walk_forward_*.json)")
    return "\n".join(lines)


def _default_notifier(message: str) -> None:
    """Ship the validation summary to Telegram, best-effort (telemetry only)."""
    try:
        send_message(message)
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Validation] telegram notification failed: %s", exc)


def _launch_walk_forward(cmd: List[str], timeout_s: int) -> subprocess.CompletedProcess:
    """Isolated subprocess seam so offline tests can stub the heavy research CLI."""
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)


def run_weekly_intraday_validation(
    *,
    notifier: Optional[Callable[[str], None]] = None,
    archive: Optional[MinuteBarArchive] = None,
    python_executable: Optional[str] = None,
    cli_path: Optional[Path] = None,
    strategy: str = DEFAULT_STRATEGY,
    timeframe: str = DEFAULT_TIMEFRAME,
    timeout_s: int = WALK_FORWARD_TIMEOUT_S,
) -> Dict[str, Any]:
    """Scheduled Sunday 10:30 job: guarded weekly intraday walk-forward.

    Never raises on exotic paths (the scheduler _safe_job wrapper catches
    anyway); every branch returns a structured result dict so the engine loop
    stays clean. The CLI itself persists the evidence artifact.
    """
    use_archive = archive if archive is not None else _DEFAULT_ARCHIVE
    notify = notifier if notifier is not None else _default_notifier
    cli = Path(cli_path) if cli_path is not None else DEFAULT_CLI_PATH

    ready, reason = intraday_validation_readiness(archive=use_archive, cadence=timeframe)
    if not ready:
        logger.info("[Validation] weekly intraday validation deferred: %s", reason)
        try:
            notify(f"Weekly intraday validation deferred -- {reason}")
        except Exception as exc:  # noqa: BLE001
            logger.warning("[Validation] deferral notification failed: %s", exc)
        return {
            "ran": False,
            "strategy": strategy,
            "timeframe": timeframe,
            "reason": reason,
        }

    py = python_executable or sys.executable
    cmd = [
        py,
        str(cli),
        "--strategy",
        strategy,
        "--timeframe",
        timeframe,
        "--tier",
        "NIFTY_50",
        "--count",
        "5",
        "--train_years",
        "1",
        "--val_years",
        "1",
        "--step_years",
        "1",
        "--embargo_days",
        "7",
        "--min_trades",
        "10",
    ]
    logger.info("[Validation] spawning intraday walk-forward: %s", " ".join(cmd))

    try:
        proc = _launch_walk_forward(cmd, timeout_s=timeout_s)
    except Exception as exc:  # noqa: BLE001
        logger.exception("[Validation] walk-forward launch failed")
        return {
            "ran": True,
            "strategy": strategy,
            "timeframe": timeframe,
            "verdict": "ERROR",
            "note": str(exc),
        }

    summary = summarize_walk_forward_run(proc.returncode, proc.stdout or "", proc.stderr or "")
    try:
        notify(_format_weekly_message(strategy, timeframe, summary))
    except Exception as exc:  # noqa: BLE001
        logger.warning("[Validation] result notification failed: %s", exc)

    return {"ran": True, "strategy": strategy, "timeframe": timeframe, **summary}