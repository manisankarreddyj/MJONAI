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
from typing import Any, Dict, Optional, Sequence

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


def _question_signature(kind: Optional[str], payload: Dict[str, Any]) -> tuple:
    """One research question = (kind, subject, window).

    CONCEPT SOURCE (clean-room from qanat's record_trial/list_trials, MIT): the
    sweep's Deflated-Sharpe haircut already charges each family for its own grid
    trials; what was missing was the JOURNAL level — how many DISTINCT questions
    have been asked, as opposed to how many runs repeat a question. A re-run with
    the same subject and window is the same question, not a second attempt.
    """
    subject = payload.get("underlying") or payload.get("symbol")
    if subject is None:
        symbols = payload.get("symbols")
        if isinstance(symbols, list) and symbols:
            head = "|".join(str(s) for s in symbols[:4])
            subject = head + ("…" if len(symbols) > 4 else "")
    window = payload.get("window") or payload.get("bars") or ""
    return (str(kind), str(subject), str(window))


def trial_summary(paths: Optional[Sequence[Path]] = None, limit: int = 200) -> Dict[str, Any]:
    """The trial journal: distinct questions, per-kind counts, verdict distribution.

    Honesty contract: verdicts are only counted where the artifact kind records one
    (the walk-forward gate does); a kind without a verdict field is reported as such
    instead of counting as a failed or missing verdict. Corrupt artifacts raise the
    `unreadable` count and never break the summary.
    """
    if paths is None:
        paths = list_evidence(limit=limit)
    if not paths:
        return {"available": False, "reason": "no verdict artifacts recorded yet — nothing has been tried"}

    signatures: set = set()
    by_kind: Dict[str, int] = {}
    verdicts: Dict[str, int] = {}
    kinds_without_verdict: set = set()
    unreadable = 0
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            payload = data.get("payload") or {}
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            unreadable += 1
            continue
        kind = str(data.get("kind") or "unknown")
        by_kind[kind] = by_kind.get(kind, 0) + 1
        signatures.add(_question_signature(kind, payload))
        verdict = payload.get("verdict")
        if verdict:
            verdicts[str(verdict)] = verdicts.get(str(verdict), 0) + 1
        else:
            kinds_without_verdict.add(kind)

    return {
        "available": True,
        "attempts": len(paths) - unreadable,
        "distinct_questions": len(signatures),
        "by_kind": dict(by_kind),
        "verdicts": verdicts,
        "kinds_without_verdict": sorted(kinds_without_verdict),
        "unreadable": unreadable,
        "note": (
            "A trial is one distinct research question (kind × subject × window); "
            "re-runs of the same question are not extra attempts. Verdicts are "
            "counted only where the kind records one — absence is not a verdict."
        ),
    }


def _flatten(obj: Any, prefix: str = "") -> Dict[str, Any]:
    """Flatten nested dicts/lists to dotted paths for diffing.

    Lists index by position (`rows.0.wfe`) — a reordered list reads as
    changed rows, which is honest for verdict artifacts (order carries
    meaning: newest-first, rank-ordered). Scalars pass through; anything
    else stringifies.
    """
    flat: Dict[str, Any] = {}
    if isinstance(obj, dict):
        for key, value in obj.items():
            path = f"{prefix}.{key}" if prefix else str(key)
            flat.update(_flatten(value, path))
    elif isinstance(obj, (list, tuple)):
        for i, value in enumerate(obj):
            flat.update(_flatten(value, f"{prefix}.{i}"))
    elif isinstance(obj, (str, int, float, bool)) or obj is None:
        flat[prefix] = obj
    else:
        flat[prefix] = str(obj)
    return flat


def diff_payloads(old: Dict[str, Any], new: Dict[str, Any],
                  max_rows: int = 60) -> Dict[str, Any]:
    """Field-level semantic diff between two artifact payloads (clean-room
    from FinRobot's provenance semantic-diff, Apache-2.0 — reimplemented,
    no code copied).

    Returns {added, removed, changed[{path, old, new, delta}], verdict_flip,
    truncated}. Numeric changes carry an absolute delta; verdict changes are
    surfaced as an explicit flip (ROBUST<->OVERFIT is the headline, not one
    row among dozens). Pure function over recorded data — nothing recomputed.
    """
    flat_old, flat_new = _flatten(old), _flatten(new)
    ko, kn = set(flat_old), set(flat_new)
    added = sorted(kn - ko)
    removed = sorted(ko - kn)
    changed = []
    for path in sorted(ko & kn):
        o, n = flat_old[path], flat_new[path]
        if o == n or (isinstance(o, float) and isinstance(n, float)
                      and abs(o - n) < 1e-9):
            continue
        row: Dict[str, Any] = {"path": path, "old": o, "new": n}
        if isinstance(o, (int, float)) and isinstance(n, (int, float)) \
                and not isinstance(o, bool) and not isinstance(n, bool):
            row["delta"] = round(n - o, 6)
        changed.append(row)
    old_v = old.get("verdict") if isinstance(old, dict) else None
    new_v = new.get("verdict") if isinstance(new, dict) else None
    verdict_flip = None
    if old_v != new_v and (old_v is not None or new_v is not None):
        verdict_flip = {"old": old_v, "new": new_v}
    truncated = len(changed) > max_rows
    return {"added": added, "removed": removed,
            "changed": changed[:max_rows], "verdict_flip": verdict_flip,
            "truncated": truncated,
            "counts": {"added": len(added), "removed": len(removed),
                       "changed": len(changed)}}


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