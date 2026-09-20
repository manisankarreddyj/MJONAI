"""Versioned research verdict evidence store tests (research/evidence.py).

These verify the fail-safe contract: evidence writes are BEST-EFFORT — a verdict
must be reproducible from artifacts when possible, and a broken evidence target
must never raise or alter a CLI exit code.
"""

import json
import sys
from pathlib import Path

_root_dir = Path(__file__).resolve().parents[2]  # repo root (ADR-0008)
if str(_root_dir) not in sys.path:
    sys.path.insert(0, str(_root_dir))

import numpy as np
import pytest

from mjonai.research.evidence import DEFAULT_EVIDENCE_DIR, SCHEMA_VERSION, record_evidence


def test_record_evidence_writes_versioned_artifact(tmp_path):
    path = record_evidence("walk_forward", {"verdict": "ROBUST", "wfe_pct": 62.5}, evidence_dir=tmp_path)
    assert path is not None
    assert path.exists()
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["schema_version"] == SCHEMA_VERSION
    assert data["kind"] == "walk_forward"
    assert data["payload"]["verdict"] == "ROBUST"
    assert "generated_at_utc" in data
    assert data["git_revision_short"]  # a rev, or honestly "unknown"
    assert data["git_revision"] in ("unknown", data["git_revision_short"]) or data["git_revision"]


def test_record_evidence_default_dir_under_repo_storage():
    assert str(DEFAULT_EVIDENCE_DIR).endswith(str(Path("storage") / "research_evidence"))


def test_record_evidence_numpy_scalars_serialize_natively(tmp_path):
    path = record_evidence(
        "forecast_benchmark",
        {"mae": np.float64(1.25), "trades": np.int64(7), "ok": np.bool_(True), "arr": np.array([1.0, 2.0])},
        evidence_dir=tmp_path,
    )
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["payload"]["mae"] == 1.25
    assert data["payload"]["trades"] == 7
    assert data["payload"]["ok"] is True
    assert data["payload"]["arr"] == [1.0, 2.0]


def test_record_evidence_never_raises_on_write_failure(tmp_path):
    blocker = tmp_path / "blocker"
    blocker.write_text("i am a file, not a directory")
    # mkdir on an existing FILE path fails -> caught -> None, never an exception.
    path = record_evidence("walk_forward", {"verdict": "ROBUST"}, evidence_dir=blocker)
    assert path is None


def test_record_evidence_unserializable_payload_survives(tmp_path):
    # A payload carrying an unresolvable object must degrade to str(), not raise.
    path = record_evidence("walk_forward", {"odd": object()}, evidence_dir=tmp_path)
    assert path is not None
    data = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(data["payload"]["odd"], str)