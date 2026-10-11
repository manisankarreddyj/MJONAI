"""
Module: research/evidence.py

Purpose: Versioned research verdict evidence store.

Every CLI verdict gate (walk-forward, forecast benchmark, ...) records a
deterministic artifact under <repo-root>/storage/research_evidence/ so a verdict
is never just a terminal print — it is persisted together with the exact
parameters and the code revision that produced it. The registry of artifacts is
therefore reproducible later ("the ROBUST verdict of 2026-09-20 was produced by
commit X, WFE=Y, N=Z trades").

Design rules:
  1. Best-effort ONLY. A failed evidence write must never fail or alter a CLI
     run — record_evidence catches everything and returns None.
  2. Storage is gitignored runtime data (storage/research_evidence/), the same
     tier as parquet caches — verdicts alone carry no secrets and are pure JSON.
  3. The git identity is best-effort metadata; if git is unavailable the
     artifact still lands with revision="unknown" rather than being dropped.
"""

from __future__ import annotations

import json
import re
import logging
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_EVIDENCE_DIR = REPO_ROOT / "storage" / "research_evidence"
SCHEMA_VERSION = 1


def _git_identity() -> Dict[str, str]:
    """Return the repo commit identity behind this verdict (best-effort)."""
    try:
        rev = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        when = subprocess.run(
            ["git", "show", "-s", "--format=%ci", "HEAD"],
            cwd=str(REPO_ROOT), capture_output=True, text=True, timeout=5,
        ).stdout.strip()
        return {
            "git_revision": rev or "unknown",
            "git_revision_short": (rev[:12] if rev else "unknown"),
            "git_commit_date": when or "unknown",
        }
    except Exception as exc:  # noqa: BLE001 — best-effort metadata
        logger.warning("[research.evidence] git identity unavailable: %s", exc)
        return {
            "git_revision": "unknown",
            "git_revision_short": "unknown",
            "git_commit_date": "unknown",
        }


def _json_default(o: Any) -> Any:
    """coerce common non-JSON scalars from research payloads to plain JSON types."""
    try:
        import numpy as np
    except ImportError:
        np = None
    if np is not None:
        if isinstance(o, np.floating):
            return float(o)
        if isinstance(o, np.integer):
            return int(o)
        if isinstance(o, np.bool_):
            return bool(o)
        if isinstance(o, np.ndarray):
            return o.tolist()
    if hasattr(o, "item"):
        return o.item()
    return str(o)


def list_evidence(kind: Optional[str] = None, limit: int = 50) -> List[Path]:
    """Versioned verdict artifacts, newest first (the research-management index).

    Reads the persisted artifact NAMES only — no payload parsing here, so a corrupt
    artifact can never break the index. Ordering uses the timestamp embedded in the
    filename (`{kind}_{YYYYMMDD}_{HHMMSS}.json`), NOT raw name order — a kind-major
    name sort would put a 2020 walk-forward above a 2026 sweep. Fail-closed: a
    missing directory returns [].
    """
    target = DEFAULT_EVIDENCE_DIR
    if not target.is_dir():
        return []
    paths = list(target.glob(f"{kind or ''}*.json"))

    def _ts(p: Path) -> str:
        m = re.search(r"(\d{8}_\d{6})(?:\.json)?$", p.name)
        return m.group(1) if m else ""

    paths.sort(key=lambda p: (_ts(p), p.name), reverse=True)
    return paths[: max(0, limit)]


def summarize_evidence(path: Path) -> Dict[str, Any]:
    """One artifact's headline fields for the research index (read-only, safe).

    Headline extraction is per-field defensive: an odd payload shape degrades that
    ONE field to None — a readable artifact is never labeled unreadable just
    because a summary field had an unexpected type (rows may be a list OR count).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # a genuinely unreadable artifact is listed as such
        return {"kind": None, "file": path.name, "error": str(exc)}
    payload = data.get("payload") or {}
    if not isinstance(payload, dict):
        payload = {}

    def _get(key):
        try:
            return payload.get(key)
        except Exception:
            return None

    rows = _get("rows")
    if isinstance(rows, (list, tuple)):
        summary_rows = len(rows)
    elif isinstance(rows, int) and not isinstance(rows, bool):
        summary_rows = rows
    else:
        summary_rows = None

    return {
        "kind": data.get("kind"),
        "generated_at_utc": data.get("generated_at_utc"),
        "git_revision_short": data.get("git_revision_short"),
        "file": path.name,
        "headline": {
            "underlying": _get("underlying"),
            "symbol": _get("symbol"),
            "families_run": _get("families_run"),
            "summary_rows": summary_rows,
        },
    }


def record_evidence(
    kind: str,
    payload: Dict[str, Any],
    evidence_dir: Optional[Path] = None,
) -> Optional[Path]:
    """
    Persist a versioned verdict artifact. Best-effort: on any write failure the
    caller's verdict is unaffected — returns None instead of raising.

    kind:      short slug for the artifact family, e.g. "walk_forward".
    payload:   JSON-serializable dict describing the run and its verdict.
    evidence_dir: injectable for tests; defaults to storage/research_evidence.
    """
    try:
        target = Path(evidence_dir) if evidence_dir is not None else DEFAULT_EVIDENCE_DIR
        target.mkdir(parents=True, exist_ok=True)
        artifact: Dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "generated_at_utc": datetime.now(timezone.utc).isoformat(),
            "kind": kind,
            "payload": payload,
        }
        artifact.update(_git_identity())
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = target / f"{kind}_{stamp}.json"
        path.write_text(json.dumps(artifact, indent=2, default=_json_default), encoding="utf-8")
        logger.info("[research.evidence] recorded %s verdict artifact -> %s", kind, path)
        return path
    except Exception as exc:  # noqa: BLE001 — evidence writes must never break the CLI
        logger.warning("[research.evidence] failed to record %s evidence artifact: %s", kind, exc)
        return None