"""
Regression pins for mjonai/core/run_logging.py (2026-10-15 owner ask):
the terminal mirror must persist every console line to a dated file and
auto-prune dirs older than 7 days — without ever touching today's dir.
"""

import datetime
import logging
import sys
from pathlib import Path

root_dir = Path(__file__).resolve().parent.parent  # repo root (ADR-0008)
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from mjonai.core import run_logging
from mjonai.core.run_logging import (
    prune_old_run_logs,
    run_log_dir,
    setup_run_file_logging,
)


def _detach_root_mirror():
    root = logging.getLogger()
    handler = getattr(root, run_logging._HANDLER_ATTR, None)
    if handler is not None:
        root.removeHandler(handler)
        try:
            handler.close()
        except Exception:
            pass
        delattr(root, run_logging._HANDLER_ATTR)


def test_setup_creates_dated_file_and_mirrors_record(tmp_path):
    _detach_root_mirror()
    try:
        day = datetime.date(2026, 10, 15)
        path = setup_run_file_logging(tmp_path, day=day)
        assert path == tmp_path / "2026-10-15" / "engine.log"
        assert path.is_file()
        logging.getLogger("MJONAI.test").warning("mirror-probe-123")
        for h in logging.getLogger().handlers:
            try:
                h.flush()
            except Exception:
                pass
        assert "mirror-probe-123" in path.read_text(encoding="utf-8")
    finally:
        _detach_root_mirror()


def test_setup_is_idempotent_no_duplicate_handler(tmp_path):
    _detach_root_mirror()
    try:
        day = datetime.date(2026, 10, 15)
        first = setup_run_file_logging(tmp_path, day=day)
        before = len(logging.getLogger().handlers)
        second = setup_run_file_logging(tmp_path, day=day)
        assert second == first
        assert len(logging.getLogger().handlers) == before
    finally:
        _detach_root_mirror()


def test_setup_fail_open_when_file_unavailable(monkeypatch, tmp_path):
    _detach_root_mirror()
    try:
        def _boom(*args, **kwargs):
            raise OSError("disk gone")

        monkeypatch.setattr(logging, "FileHandler", _boom)
        assert setup_run_file_logging(tmp_path) is None
    finally:
        _detach_root_mirror()


def _make_day(root: Path, day: datetime.date):
    d = root / day.isoformat()
    d.mkdir(parents=True, exist_ok=True)
    (d / "engine.log").write_text("x", encoding="utf-8")
    return d


def test_prune_keeps_7_days_deletes_older(tmp_path):
    today = datetime.date(2026, 10, 15)
    keep = [today - datetime.timedelta(days=n) for n in range(0, 8)]  # 0..7
    drop = [today - datetime.timedelta(days=n) for n in (8, 9, 30)]
    for d in keep + drop:
        _make_day(tmp_path, d)
    pruned = prune_old_run_logs(tmp_path, today=today)
    assert sorted(p.name for p in pruned) == sorted(d.isoformat() for d in drop)
    for d in keep:
        assert (tmp_path / d.isoformat()).is_dir()
    for d in drop:
        assert not (tmp_path / d.isoformat()).exists()


def test_prune_never_touches_today_nor_junk(tmp_path):
    today = datetime.date(2026, 10, 15)
    _make_day(tmp_path, today)
    (tmp_path / "2026-13-99").mkdir()  # impossible calendar date
    (tmp_path / "scratch").mkdir()  # non-date entry
    (tmp_path / "notes.txt").write_text("keep", encoding="utf-8")
    pruned = prune_old_run_logs(tmp_path, today=today)
    assert pruned == []
    assert (tmp_path / today.isoformat()).is_dir()
    assert (tmp_path / "scratch").is_dir()
    assert (tmp_path / "notes.txt").is_file()


def test_prune_missing_root_is_empty(tmp_path):
    assert prune_old_run_logs(tmp_path / "nope") == []


def test_run_log_dir_layout():
    assert run_log_dir("logs", datetime.date(2026, 10, 15)) == Path("logs/2026-10-15")
