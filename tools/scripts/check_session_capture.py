"""
Script: tools/scripts/check_session_capture.py
Purpose: Continuity guard -- detects CODE WORK THAT WAS NEVER RECORDED.

Why this exists
---------------
On 2026-09-27 a single unrecorded session produced ~2,853 lines (a research
harness, 7 CLIs, 2 test files, a 497-symbol data backfill). Nothing was
committed, nothing was written to MJONAI_DOCS.md, and the session-memory
plugin had silently stopped 12 days earlier -- so for 7 days the work sat
untracked and its conclusion was unrecoverable. The 20-day silent gap was
the real defect; the lost work was the symptom.

The session-memory plugin (`.opencode/plugin/session-memory.ts`) swallows
every error by design, so its failure is invisible from the plugin side.
This guard therefore never inspects the capture MECHANISM. It checks the
OUTCOME, which is mechanism-independent: a date that carries real code work
must be evidenced by EITHER a raw session log OR an MJONAI_DOCS.md mention.
Neither means the work left no trace.

Two distinct ways work is lost, and BOTH are checked:
  1. COMMITTED BUT UNRECORDED -- a commit carrying code whose date appears in
     neither the raw logs nor MJONAI_DOCS.md.
  2. NEVER COMMITTED -- modified/untracked code in the working tree. This is
     the 2026-09-27 case exactly: 33 untracked paths, zero commits, so a
     commit-date scan alone would have missed it. Uncommitted code work is
     unrecorded by definition and is reported on its own channel.

Honesty of the check
--------------------
  - A missing raw session log is NOT by itself a finding. Raw logs are
    ADR-0009 layer-3, gitignored, and explicitly NON-authoritative; the
    authoritative record is MJONAI_DOCS.md section 16. A session may be
    perfectly well documented with no raw capture.
  - Only CODE work is flagged. Doc-only, archive-only, and testdata-only
    changes legitimately need no session record and must never churn this
    guard.
  - In CI (no local capture store -- cache/ is gitignored) the guard reports
    SKIP for the capture channel and exits 0. It cannot verify there, so it
    must not fail there. The uncommitted-code channel still applies.

Usage: python tools/scripts/check_session_capture.py [--commits N] [--strict]
Exit code: 1 = unrecorded code work found (or --strict with capture stale),
            0 = every code-work date is evidenced, 2 = git unavailable.
"""

from __future__ import annotations

import argparse
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
SESSION_ROOT = REPO_ROOT / "cache" / "sessions"
DOC_PATH = REPO_ROOT / "MJONAI_DOCS.md"

# Commits touching only these are NOT "code work" and never require a record.
_NON_CODE_PREFIXES = (
    "docs_archive/", "archive/", "cache/", "storage/", "logs/", "backups/",
    "datasets/",
)
_NON_CODE_SUFFIXES = (".md", ".txt", ".csv", ".log")

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


def _git(*args: str) -> Optional[str]:
    """Run a git command in the repo; None on any failure."""
    try:
        proc = subprocess.run(
            ["git", *args], cwd=str(REPO_ROOT),
            capture_output=True, text=True, timeout=30,
        )
    except Exception:
        return None
    if proc.returncode != 0:
        return None
    return proc.stdout


def _is_code_work(path: str) -> bool:
    """True when a changed path represents real engine/research/tooling code."""
    norm = path.replace("\\", "/").strip()
    if not norm:
        return False
    if norm.startswith(_NON_CODE_PREFIXES):
        return False
    low = norm.lower()
    if low.endswith(_NON_CODE_SUFFIXES):
        return False
    return True


def code_work_dates(max_commits: int = 400) -> Dict[str, List[str]]:
    """Map ISO date -> changed code paths, for dates that carry code work.

    Walks `git log --name-only` once and groups by author date. Non-code
    paths are filtered out; a date with no surviving path is not a code-work
    date and is omitted entirely.
    """
    raw = _git("log", f"-n{max_commits}", "--name-only", "--format=@@%as")
    if raw is None:
        return {}

    by_date: Dict[str, List[str]] = defaultdict(list)
    current: Optional[str] = None
    for line in raw.splitlines():
        if line.startswith("@@"):
            candidate = line[2:].strip()
            current = candidate if _ISO_DATE.match(candidate) else None
            continue
        if current and _is_code_work(line):
            by_date[current].append(line.strip())

    return {d: sorted(set(p)) for d, p in by_date.items()}


def capture_dates() -> Set[str]:
    """ISO dates that have a raw session log on disk."""
    if not SESSION_ROOT.is_dir():
        return set()
    return {p.stem for p in SESSION_ROOT.glob("*.jsonl") if _ISO_DATE.match(p.stem)}


def documented_dates() -> Set[str]:
    """ISO dates literally cited in MJONAI_DOCS.md (the authoritative record)."""
    try:
        text = DOC_PATH.read_text(encoding="utf-8")
    except OSError:
        return set()
    return set(re.findall(r"\b\d{4}-\d{2}-\d{2}\b", text))


def uncommitted_code_paths() -> List[str]:
    """Code paths that are modified or untracked in the working tree.

    This is the 2026-09-27 failure mode: the session produced real code and
    never committed it, so no commit-date scan could ever see it. Uncommitted
    code work is unrecorded by definition.
    """
    raw = _git("status", "--porcelain")
    if raw is None:
        return []
    found: List[str] = []
    for line in raw.splitlines():
        if len(line) < 4:
            continue
        path = line[3:].strip().strip('"')
        # Rename/copy entries carry "old -> new"; judge the destination.
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        if _is_code_work(path):
            found.append(path.replace("\\", "/"))
    return sorted(set(found))


def analyse(max_commits: int = 400) -> Tuple[List[Tuple[str, List[str]]], bool]:
    """Return (unrecorded, capture_store_present)."""
    work = code_work_dates(max_commits)
    if not work and _git("rev-parse", "HEAD") is None:
        return [], False
    captured = capture_dates()
    documented = documented_dates()
    unrecorded = [
        (date, paths)
        for date, paths in sorted(work.items())
        if date not in captured and date not in documented
    ]
    return unrecorded, SESSION_ROOT.is_dir()


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Session-capture continuity guard")
    parser.add_argument("--commits", type=int, default=400,
                        help="how many commits to inspect (default 400)")
    parser.add_argument("--strict", action="store_true",
                        help="also fail when the newest capture is more than "
                             "7 days older than the newest code-work date")
    args = parser.parse_args(list(argv) if argv is not None else None)

    if _git("rev-parse", "--git-dir") is None:
        print("session-capture: SKIP -- not a git repository")
        return 2

    work = code_work_dates(args.commits)
    if not work:
        print("session-capture: no code-work commits found -- OK")
        return 0

    captured = capture_dates()
    documented = documented_dates()
    store_present = SESSION_ROOT.is_dir()

    unrecorded = [
        (date, paths) for date, paths in sorted(work.items())
        if date not in captured and date not in documented
    ]

    label = "session-capture"
    print(
        f"{label}: inspected {len(work)} code-work date(s); "
        f"capture store {'present' if store_present else 'ABSENT (CI)'}; "
        f"{len(captured)} raw log(s)"
    )

    if not store_present:
        print(
            f"{label}: SKIP -- cache/sessions is gitignored and absent here, "
            "so raw capture cannot be verified. Docs-evidenced dates: "
            f"{sum(1 for d in work if d in documented)}/{len(work)}."
        )
    else:
        if unrecorded:
            print(f"{label}: FAILED -- code work on {len(unrecorded)} date(s) left no trace:")
            for date, paths in unrecorded:
                print(f"  - {date}: {len(paths)} code path(s), e.g. {paths[0]}")
        else:
            print(f"{label}: OK -- every code-work date has a raw log or a docs entry")

    # Channel 2: uncommitted code work (the 2026-09-27 loss mode).
    uncommitted = uncommitted_code_paths()
    if uncommitted:
        print(
            f"{label}: FAILED -- {len(uncommitted)} code path(s) are modified or "
            "untracked and therefore recorded nowhere:"
        )
        for path in uncommitted[:20]:
            print(f"  - {path}")
        if len(uncommitted) > 20:
            print(f"  ... and {len(uncommitted) - 20} more")
        print(
            f"{label}: commit them, archive them, or delete them -- uncommitted "
            "code is unrecoverable if this machine is lost."
        )
        return 1

    if not store_present:
        return 0

    if unrecorded:
        print(
            f"{label}: record the dates above in MJONAI_DOCS.md section 16 "
            "(authoritative) or append a raw log via "
            "`python tools/scripts/session_memory.py append`. "
            "Do not silence this guard."
        )
        return 1

    if args.strict and captured and work:
        newest_work = max(work)
        newest_cap = max(captured)
        if newest_cap < newest_work:
            gap_days = (_date(newest_work) - _date(newest_cap)).days
            if gap_days > 7:
                print(
                    f"{label}: FAILED (--strict) -- newest capture {newest_cap} "
                    f"is {gap_days} days older than newest code-work date "
                    f"{newest_work}; the capture plugin is likely not loading."
                )
                return 1
    return 0


def _date(value: str):
    from datetime import date as _d
    return _d.fromisoformat(value)


if __name__ == "__main__":
    sys.exit(main())
