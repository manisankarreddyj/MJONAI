"""Regression tests: docs-drift guard (dev/ops loop Phase 2).

The guard (tools/scripts/check_docs_refs.py) runs in CI on every push/PR
(.github/workflows/deterministic-ci.yml `docs-drift` job) and nightly. The
live MJONAI_DOCS.md must stay green; other fixtures pin the guard's own
behavior (flags a real missing path, ignores runtime/prose refs)."""

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT = REPO_ROOT / "tools" / "scripts" / "check_docs_refs.py"


def _run(doc: Path):
    return subprocess.run(
        [sys.executable, str(SCRIPT), str(doc)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        timeout=60,
    )


def test_docs_refs_green_on_live_doc():
    """The live master doc must cite only paths that exist in the repo."""
    proc = _run(REPO_ROOT / "MJONAI_DOCS.md")
    assert proc.returncode == 0, f"docs-drift guard failed:\n{proc.stdout}\n{proc.stderr}"


def test_docs_refs_flags_real_missing_path(tmp_path):
    doc = tmp_path / "FAKE_DOC.md"
    doc.write_text(
        "See `MJONAI_DOCS.md` and also `apps/runtime/definitely_removed.py`.\n",
        encoding="utf-8",
    )
    proc = _run(doc)
    assert proc.returncode == 1
    assert "definitely_removed.py" in proc.stdout


def test_docs_refs_ignores_runtime_and_prose(tmp_path):
    doc = tmp_path / "FAKE_DOC.md"
    doc.write_text(
        "`storage/parquet/REL/1m_raw.parquet` and `FII/DII` and `MJONAI_DOCS.md`\n",
        encoding="utf-8",
    )
    proc = _run(doc)
    assert proc.returncode == 0, proc.stdout + proc.stderr