"""
Module: mjonai/core/run_logging.py
Purpose: Engine-owned terminal mirror — every console log line is also
         persisted to a dated file so a closed terminal (or a manual
         copy-paste, as on 2026-10-15) can never lose the debug record.

Layout: <repo>/logs/YYYY-MM-DD/engine.log  (UTF-8, append).
Retention: keep the newest RETENTION_DAYS date dirs, auto-prune older ones
         at startup. Today's dir is never pruned. Non-date entries ignored.

Security: local only — logs/ is gitignored (*.log + logs/). No secrets are
ever written here that are not already on the console (same records).
"""

import datetime as _dt
import logging as _logging
import re as _re
from pathlib import Path as _Path
from typing import List, Optional, Union

logger = _logging.getLogger(__name__)

RETENTION_DAYS = 7
ENGINE_LOG_FILENAME = "engine.log"
_DATE_DIR_RE = _re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")

_HANDLER_ATTR = "_mjonai_run_file_handler"


def _today() -> _dt.date:
    return _dt.datetime.now().date()


def run_log_dir(logs_root: Union[str, _Path], day: Optional[_dt.date] = None) -> _Path:
    """Dated directory for one engine day: logs/YYYY-MM-DD."""
    day = day or _today()
    return _Path(logs_root) / day.isoformat()


def setup_run_file_logging(
    logs_root: Union[str, _Path] = "logs",
    day: Optional[_dt.date] = None,
) -> Optional[_Path]:
    """
    Attach a UTF-8 append FileHandler for logs/YYYY-MM-DD/engine.log to the
    ROOT logger, so every record that reaches the console is also persisted.
    Idempotent within a process (a second call is a no-op returning the path).
    Returns the log path, or None if the file cannot be opened (console
    logging is unaffected — logging must never kill the engine).
    """
    root = _logging.getLogger()
    existing = getattr(root, _HANDLER_ATTR, None)
    if existing is not None:
        return getattr(existing, "_mjonai_log_path", None)

    day = day or _today()
    path = run_log_dir(logs_root, day) / ENGINE_LOG_FILENAME
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = _logging.FileHandler(str(path), mode="a", encoding="utf-8")
        handler.setLevel(_logging.DEBUG)
        handler.setFormatter(
            _logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%H:%M:%S",
            )
        )
        handler._mjonai_log_path = path  # type: ignore[attr-defined]
        root.addHandler(handler)
        setattr(root, _HANDLER_ATTR, handler)
        return path
    except Exception as e:  # fail-open on the file side only
        logger.debug(f"[run_logging] file mirror unavailable ({e}) — console only")
        return None


def prune_old_run_logs(
    logs_root: Union[str, _Path] = "logs",
    retention_days: int = RETENTION_DAYS,
    today: Optional[_dt.date] = None,
) -> List[_Path]:
    """
    Delete logs/YYYY-MM-DD dirs older than retention_days. Pure by date-dir
    name (no mtime dependence). Today's dir is never pruned even if the clock
    looks odd; non-date entries are ignored. Returns pruned dirs.
    """
    root = _Path(logs_root)
    today = today or _today()
    if not root.is_dir():
        return []
    cutoff = today - _dt.timedelta(days=retention_days)
    pruned: List[_Path] = []
    for child in sorted(root.iterdir()):
        if not child.is_dir():
            continue
        m = _DATE_DIR_RE.match(child.name)
        if not m:
            continue
        try:
            dir_day = _dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        except ValueError:
            continue  # impossible calendar date — leave it, never delete blind
        if dir_day == today:
            continue
        if dir_day < cutoff:
            try:
                import shutil as _shutil

                _shutil.rmtree(child)
                pruned.append(child)
            except Exception as e:
                logger.debug(f"[run_logging] prune skipped {child} ({e})")
    return pruned
