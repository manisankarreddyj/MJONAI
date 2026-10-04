"""Regression tests: session-capture continuity guard.

The guard (tools/scripts/check_session_capture.py) exists because the
2026-09-27 session left ~2,853 lines of real code with no commit, no docs
entry, and no raw capture -- a 7-day silent loss. These tests pin both of
the guard's detection channels and, critically, its HONESTY: a doc-only or
archived change must never be flagged, and CI (where cache/ is absent) must
skip rather than fail.
"""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "scripts" / "check_session_capture.py"

sys.path.insert(0, str(REPO_ROOT / "tools" / "scripts"))
import check_session_capture as guard  # noqa: E402


def _run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=120,
    )


# ── classification: what counts as "code work" ─────────────────────────────────

def test_code_paths_are_code_work():
    for path in (
        "mjonai/research/discovery/harness.py",
        "apps/research/run_cs_sweep.py",
        "tools/scripts/forward_sim_deep.py",
        "tests/research/test_cross_sectional.py",
    ):
        assert guard._is_code_work(path), path


def test_docs_and_archives_are_never_code_work():
    """Doc/archive/testdata churn must not churn this guard."""
    for path in (
        "MJONAI_DOCS.md",
        "README.md",
        "docs_archive/review_logs_2026_08/AUDIT.md",
        "archive/scratch/notes.txt",
        "cache/sessions/2026-09-14.jsonl",
        "storage/parquet/tradingtick_index/spot/NIFTY/2014-01.parquet",
        "mjonai/data/angelone/nifty500_tokens.csv",
    ):
        assert not guard._is_code_work(path), path


def test_windows_style_paths_are_normalised():
    assert guard._is_code_work("mjonai\\risk\\emergency_triggers.py")
    assert not guard._is_code_work("docs_archive\\old.md")


# ── channel 1: committed-but-unrecorded code work ─────────────────────────────

def test_code_work_dates_groups_by_date(tmp_path, monkeypatch):
    """A commit touching only docs yields NO code-work date."""
    repo = tmp_path / "repo"
    (repo / "mjonai").mkdir(parents=True)
    (repo / "docs_archive").mkdir()
    env = {"GIT_AUTHOR_DATE": "2026-09-27T10:00:00", "GIT_COMMITTER_DATE": "2026-09-27T10:00:00"}

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                              text=True, env={**dict(__import__("os").environ), **env}, timeout=30)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "docs_archive" / "a.md").write_text("x", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "docs only")

    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    assert guard.code_work_dates() == {}

    (repo / "mjonai" / "x.py").write_text("y = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "code")
    dates = guard.code_work_dates()
    assert "2026-09-27" in dates
    assert dates["2026-09-27"] == ["mjonai/x.py"]


# ── channel 2: never-committed code work (the 2026-09-27 loss mode) ───────────

def test_uncommitted_code_paths_detects_untracked_python(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "keep.txt").write_text("x", encoding="utf-8")

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                              text=True, timeout=30)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "init")

    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    assert guard.uncommitted_code_paths() == []

    (repo / "scratch.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "NOTES.md").write_text("notes\n", encoding="utf-8")
    assert guard.uncommitted_code_paths() == ["scratch.py"]


# ── honesty: CI must skip, not fail ───────────────────────────────────────────

def test_ci_without_capture_store_skips_and_exits_zero(tmp_path, monkeypatch, capsys):
    """cache/ is gitignored, so a CI checkout has no capture store. The guard
    must report SKIP and exit 0 -- it cannot verify there, so it must not
    fail there."""
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "config", "user.email", "t@t.t"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "config", "user.name", "t"], cwd=str(repo), capture_output=True, timeout=30)
    (repo / "a.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=str(repo), capture_output=True, timeout=30)
    subprocess.run(["git", "commit", "-q", "-m", "c"], cwd=str(repo), capture_output=True, timeout=30)

    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    monkeypatch.setattr(guard, "SESSION_ROOT", repo / "cache" / "sessions")
    monkeypatch.setattr(guard, "DOC_PATH", repo / "MJONAI_DOCS.md")

    rc = guard.main([])
    out = capsys.readouterr().out
    assert rc == 0, out
    assert "SKIP" in out


def test_guard_detects_unrecorded_code_work(tmp_path, monkeypatch, capsys):
    """A code commit whose date is in neither the raw logs nor the docs must
    fail the guard -- this is the exact 2026-09-27 shape (recorded nowhere)."""
    repo = tmp_path / "repo"
    repo.mkdir()
    env_date = "2026-09-27"
    import os
    env = {**os.environ, "GIT_AUTHOR_DATE": f"{env_date}T10:00:00",
           "GIT_COMMITTER_DATE": f"{env_date}T10:00:00"}

    def git(*args):
        return subprocess.run(["git", *args], cwd=str(repo), capture_output=True,
                              text=True, env=env, timeout=30)

    git("init", "-q")
    git("config", "user.email", "t@t.t")
    git("config", "user.name", "t")
    (repo / "mjonai").mkdir()
    (repo / "mjonai" / "x.py").write_text("y = 1\n", encoding="utf-8")
    git("add", "-A")
    git("commit", "-q", "-m", "code")
    # An empty capture store so the capture channel is active.
    (repo / "cache" / "sessions").mkdir(parents=True)

    monkeypatch.setattr(guard, "REPO_ROOT", repo)
    monkeypatch.setattr(guard, "SESSION_ROOT", repo / "cache" / "sessions")
    monkeypatch.setattr(guard, "DOC_PATH", repo / "MJONAI_DOCS.md")  # absent

    rc = guard.main([])
    out = capsys.readouterr().out
    assert rc == 1, out
    assert env_date in out
