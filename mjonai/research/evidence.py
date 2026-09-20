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