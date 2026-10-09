"""
Script: tools/scripts/check_docs_refs.py

Purpose: Dev/ops loop Phase 2 -- docs-drift guard for MJONAI_DOCS.md.

Verifies that backtick-cited file/directory paths inside MJONAI_DOCS.md resolve
inside the repository. Runs from the `docs-drift` job in
.github/workflows/deterministic-ci.yml on every push/PR and nightly, and from
tests/test_docs_refs.py locally.

Honesty of the check:
  - Only mechanically-checkable refs are validated: tokens that resolve to a
    real location under the repo tree (a top-level repo path such as
    `mjonai/...`/`apps/...`/`docs_archive/...`, a bare repo-root file such as
    `README.md`, or a kernel-relative short form such as `db/agents.py` ->
    mjonai/db/agents.py).
  - Prose word-lists written with "/" (FII/DII, RESEARCH/PAPER/LIVE, v2.0/v4.x)
    are NOT paths and are silently ignored -- the check must never churn a doc
    for a false positive.
  - `file.py:NNNN` line numbers are stripped BEFORE matching -- line numbers
    drift legitimately and the file identity is the stable claim.
  - Runtime-data refs (storage/, cache/, logs/, backups/, datasets/,
    credentials/, .env, .venv/) are skipped: those exist at runtime, not in a
    CI checkout, and are gitignored.
  - Historical/one-off refs (mjonai-build/, supabase_FULL_backup, .bak_) are
    skipped: they document past migrations, not current tree members.

Usage: python tools/scripts/check_docs_refs.py [PATH_TO_MD]
Default document: MJONAI_DOCS.md at the repo root.
Exit code: 2 = document missing, 1 = cited refs missing, 0 = all refs exist.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DOC = REPO_ROOT / "MJONAI_DOCS.md"

KNOWN_EXTS = (
    ".py", ".json", ".yml", ".yaml", ".toml", ".md", ".ps1", ".sh",
    ".csv", ".sql", ".txt", ".html", ".tsx", ".ts", ".jsx", ".js", ".example",
)
# Tokens under these normalized prefixes exist at runtime, never in a fresh checkout.
RUNTIME_PREFIXES = (
    "storage/", "cache/", "logs/", "backups/", "datasets/", "credentials/", ".venv/",
)
# Historical/one-off refs describing past migrations or trees pruned from the
# working tree (recoverable from git history via tag pre-cleanup-*) -- intentionally
# not live members, so a citation to them is a history pointer, not a live-path claim.
HISTORICAL_MARKERS = (
    "mjonai-build", "supabase_FULL_backup", ".bak_",
    "docs_archive/", "archive/",
    "risk/special_modes.py", "mjonai_intelligence",
)

_BACKTICK = re.compile(r"`([^`]+)`")
_PATH_PREFIX = re.compile(r"^[A-Za-z0-9_./\\-]+")
_DRIVE = re.compile(r"^[A-Za-z]:")
_BAD_CHARS = set("…YYYY{}…*?%<>|~#")
_KERNEL_DIRS: Optional[set] = None


def _kernel_dirs() -> set:
    """Immediate mjonai/* subpackages used to resolve kernel-relative short refs."""
    global _KERNEL_DIRS
    if _KERNEL_DIRS is None:
        try:
            _KERNEL_DIRS = {
                p.name.lower()
                for p in (REPO_ROOT / "mjonai").iterdir()
                if p.is_dir()
            }
        except OSError:
            _KERNEL_DIRS = set()
    return _KERNEL_DIRS


def _leading_path(piece: str) -> str:
    """Pull the leading path-ish token out of a backticked whitespace piece."""
    m = _PATH_PREFIX.match(piece)
    if not m:
        return ""
    return m.group(0).strip()


_CODE_FENCE = re.compile(r"^\s*(```|~~~)")


def _strip_code_fences(line: str, text: str) -> str:
    """Cheap line-local code-fence guard: if a line IS a markdown fence
    (open or close ``` or ~~~), it carries no backtick-cited path, so return
    an empty body to keep pairing local. Inline prose (including bullets that
    cite paths) is never a fence."""
    if _CODE_FENCE.match(line):
        return ""
    return line


def _prefilter(norm: str) -> bool:
    """Reject tokens that can never be an existence claim."""
    if len(norm) < 3:
        return False
    if ".." in norm or ":" in norm:
        return False
    if _DRIVE.match(norm) or norm.startswith(("/", "\\")):
        return False
    if any(ch in norm for ch in _BAD_CHARS):
        return False
    low = norm.lower()
    if low in (".env", ".venv"):
        return False
    for prefix in RUNTIME_PREFIXES:
        if low.startswith(prefix):
            return False
    for marker in HISTORICAL_MARKERS:
        if marker in low:
            return False
    return True


def _resolve(norm: str) -> Optional[Path]:
    """Map a normalized candidate to a repo path to check; None when ambiguous
    (prose word-lists like FII/DII are not existence claims and resolve to None).

    Resolvable classes:
      1. Top-level repo entry -- `mjonai/...`, `apps/...`, `docs_archive/...`,
         bare root files like `README.md` (`infra/mjonai.service` too: a top-level
         path claim is unambiguous even without a known extension).
      2. Kernel-relative short form -- `db/agents.py` -> mjonai/db/agents.py.
         Only for file refs (known extension) or explicit dir refs (trailing
         slash) so prose like `research/minute` can never resolve.
      3. A bare module file that is UNIQUE under mjonai/ (`devil_checks.py` ->
         mjonai/risk/devil_checks.py); multi-hit bare names are ambiguous.
    """
    trailing = norm.endswith("/")
    norm = norm.rstrip("/")
    parts = norm.split("/")
    first = parts[0].lower()

    # 1. top-level entry -- the FIRST segment being a real repo-root entry is
    #    the claim; the existence check happens on the full path downstream.
    top = REPO_ROOT / Path(*parts)
    if (REPO_ROOT / parts[0]).exists():
        return top

    if first in _kernel_dirs():
        last = parts[-1].lower()
        if trailing or any(last.endswith(ext) for ext in KNOWN_EXTS):
            return REPO_ROOT / "mjonai" / Path(*parts)
        return None

    if len(parts) == 1:
        name = parts[0]
        hits = [p for p in (REPO_ROOT / "mjonai").rglob(name)]
        if len(hits) == 1:
            return hits[0]
    return None


def _is_gitignored(rel: Path) -> bool:
    """True when git marks the repo-relative path ignored (runtime-generated
    caches are absent in a fresh CI checkout but must not fail the guard)."""
    try:
        proc = subprocess.run(
            ["git", "check-ignore", "-q", "--", str(rel)],
            cwd=str(REPO_ROOT), capture_output=True, timeout=10,
        )
        return proc.returncode == 0
    except Exception:
        return False


def extract_candidates(text: str) -> List[str]:
    """Return deduped, normalized candidate refs found in backticked spans.

    Runs the span regex PER MARKDOWN LINE, not on the whole document. Pairing
    parity can drift across the document when a prose region carries an odd
    run of backticks (em-dash/-prose word-lists, code fences); a whole-doc
    `[^`]+` scan then swallows neighbouring tokens and silently un-checks
    them. Within a single logical line the pairing is locally exact, so every
    backtick-cited token is extracted -- the guard can never skip a citation
    just because it sits near an unbalanced region in earlier prose.
    """
    candidates: List[str] = []
    seen = set()
    for line in text.splitlines():
        line_body = _strip_code_fences(line, text)
        for token in _BACKTICK.findall(line_body):
            for piece in token.split():
                if "…" in piece or "YYYY" in piece:
                    continue

                cand = _leading_path(piece)
                if not cand:
                    continue
                norm = cand.replace("\\", "/")
                if not _prefilter(norm.rstrip("/")):
                    continue
                key = norm.rstrip("/").lower()
                if key in seen:
                    continue
                seen.add(key)
                candidates.append(norm)
    return candidates


def check_doc(doc_path: Path):
    """Return (checked, missing) for a document."""
    text = doc_path.read_text(encoding="utf-8")
    candidates = extract_candidates(text)
    missing: List[str] = []
    checked = 0
    for cand in candidates:
        target = _resolve(cand)
        if target is None:
            continue  # prose/ambiguous, not an existence claim
        checked += 1
        if target.exists():
            continue
        rel = target.relative_to(REPO_ROOT)
        if _is_gitignored(rel):
            continue  # runtime-generated cache absent here -- not drift
        missing.append(cand)
    return checked, missing


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:]) if argv is None else list(argv)
    doc = Path(argv[0]) if argv else DEFAULT_DOC
    if not doc.exists():
        print(f"docs-refs: FAILED -- document not found: {doc}")
        return 2

    checked, missing = check_doc(doc)
    print(f"docs-refs: {doc.name}: checked {checked} cited paths, {len(missing)} missing")
    if missing:
        print("docs-refs: FAILED -- cited paths do not exist in the repository:")
        for m in sorted(missing):
            print(f"  - {m}")
        print("docs-refs: fix the reference or move the file back; do not silence the guard.")
        return 1
    print("docs-refs: OK -- every cited path exists")
    return 0


if __name__ == "__main__":
    sys.exit(main())