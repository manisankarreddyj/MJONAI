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

import mjonai.research.evidence as ev
from mjonai.research.evidence import (
    DEFAULT_EVIDENCE_DIR,
    SCHEMA_VERSION,
    diff_payloads,
    list_evidence,
    record_evidence,
    summarize_evidence,
)


# ── SEMANTIC DIFF (FinRobot provenance pattern, clean-room) ─────────────────

def test_diff_payloads_added_removed_changed_with_delta():
    old = {"verdict": "OVERFIT", "wfe_pct": 12.5, "gone": 1,
           "overall": {"oos": -3.0, "trades": 40}}
    new = {"verdict": "ROBUST", "wfe_pct": 61.0, "fresh": 2,
           "overall": {"oos": 4.5, "trades": 40}}
    d = diff_payloads(old, new)
    assert d["verdict_flip"] == {"old": "OVERFIT", "new": "ROBUST"}
    assert d["added"] == ["fresh"] and d["removed"] == ["gone"]
    by_path = {c["path"]: c for c in d["changed"]}
    assert by_path["wfe_pct"]["delta"] == round(61.0 - 12.5, 6)
    assert by_path["overall.oos"]["delta"] == 7.5
    assert "overall.trades" not in by_path  # unchanged rows stay silent
    assert d["counts"] == {"added": 1, "removed": 1, "changed": 3}
    assert d["truncated"] is False


def test_diff_payloads_empty_and_identical():
    d = diff_payloads({}, {})
    assert d["counts"] == {"added": 0, "removed": 0, "changed": 0}
    assert d["verdict_flip"] is None
    same = {"a": 1, "b": [1, 2]}
    assert diff_payloads(same, {"a": 1, "b": [1, 2]})["counts"]["changed"] == 0


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


def test_list_evidence_without_kind_never_raises(tmp_path, monkeypatch):
    # REGRESSION (2026-10-11): the glob pattern used to interpolate to "**.json",
    # which pathlib rejects ("'**' can only be an entire path component") — the
    # research index was dead on arrival until this ran green.
    import mjonai.research.evidence as ev

    monkeypatch.setattr(ev, "DEFAULT_EVIDENCE_DIR", tmp_path)
    record_evidence("walk_forward", {"verdict": "ROBUST"}, evidence_dir=tmp_path)
    record_evidence("discovery_sweep", {"rows": 1}, evidence_dir=tmp_path)
    paths = ev.list_evidence(limit=10)
    assert len(paths) == 2


def test_list_evidence_sorts_chronologically_not_kind_alphabetically(tmp_path, monkeypatch):
    # Name-desc sort would wrongly put walk_forward_2020 ABOVE discovery_sweep_2026
    # ('w' > 'd') — ordering must use the embedded timestamp.
    import mjonai.research.evidence as ev

    monkeypatch.setattr(ev, "DEFAULT_EVIDENCE_DIR", tmp_path)
    (tmp_path / "walk_forward_20200101_000000.json").write_text(
        json.dumps({"kind": "walk_forward", "payload": {}}), encoding="utf-8")
    (tmp_path / "discovery_sweep_20261011_000000.json").write_text(
        json.dumps({"kind": "discovery_sweep", "payload": {}}), encoding="utf-8")
    paths = ev.list_evidence()
    assert [p.name for p in paths] == [
        "discovery_sweep_20261011_000000.json",
        "walk_forward_20200101_000000.json",
    ]


def test_list_evidence_kind_filter_and_empty_dir(tmp_path, monkeypatch):
    import mjonai.research.evidence as ev

    monkeypatch.setattr(ev, "DEFAULT_EVIDENCE_DIR", tmp_path)
    assert ev.list_evidence() == []  # empty dir -> [], fail-closed, never raises
    record_evidence("walk_forward", {"verdict": "ROBUST"}, evidence_dir=tmp_path)
    record_evidence("forecast_benchmark", {"mae": 1.0}, evidence_dir=tmp_path)
    only_wf = ev.list_evidence(kind="walk_forward")
    assert [p.name for p in only_wf] == [p.name for p in only_wf if p.name.startswith("walk_forward")]
    assert len(only_wf) == 1


def test_summarize_evidence_corrupt_artifact_listed_not_skipped(tmp_path):
    bad = tmp_path / "corrupt_20261011.json"
    bad.write_text("{not json", encoding="utf-8")
    summary = summarize_evidence(bad)
    assert summary["file"] == bad.name
    assert summary["error"]  # listed as unreadable — never silently dropped
    good = record_evidence("walk_forward", {"verdict": "OVERFIT"}, evidence_dir=tmp_path)
    ok = summarize_evidence(good)
    assert ok["kind"] == "walk_forward"
    assert ok["git_revision_short"]


# ── the trial journal (qanat list_trials/record_trial concept, clean-room) ─────
def test_trial_summary_dedups_distinct_questions(tmp_path):
    ev.DEFAULT_EVIDENCE_DIR = tmp_path
    # three attempts, TWO distinct questions: same (kind, subject, window) twice
    (tmp_path / "walk_forward_20260101_000000.json").write_text(json.dumps(
        {"kind": "walk_forward", "payload": {"symbols": ["RELIANCE"], "verdict": "ROBUST"}}), "utf-8")
    (tmp_path / "walk_forward_20260102_000000.json").write_text(json.dumps(
        {"kind": "walk_forward", "payload": {"symbols": ["RELIANCE"], "verdict": "OVERFIT"}}), "utf-8")
    (tmp_path / "walk_forward_20260103_000000.json").write_text(json.dumps(
        {"kind": "walk_forward", "payload": {"symbols": ["TCS"], "verdict": "ROBUST"}}), "utf-8")
    t = ev.trial_summary()
    assert t["available"] is True
    assert t["attempts"] == 3
    assert t["distinct_questions"] == 2  # RELIANCE-repeat is ONE question
    assert t["verdicts"] == {"ROBUST": 2, "OVERFIT": 1}
    assert t["unreadable"] == 0


def test_trial_summary_reports_kinds_without_verdict_honestly(tmp_path):
    ev.DEFAULT_EVIDENCE_DIR = tmp_path
    (tmp_path / "discovery_sweep_20260101_000000.json").write_text(json.dumps(
        {"kind": "discovery_sweep", "payload": {"underlying": "NIFTY", "bars": 100}}), "utf-8")
    t = ev.trial_summary()
    assert t["by_kind"] == {"discovery_sweep": 1}
    assert t["verdicts"] == {}  # records no verdict — absence is NOT a verdict
    assert t["kinds_without_verdict"] == ["discovery_sweep"]


def test_trial_summary_empty_dir_is_fail_closed(tmp_path):
    ev.DEFAULT_EVIDENCE_DIR = tmp_path
    t = ev.trial_summary()
    assert t["available"] is False
    assert "nothing has been tried" in t["reason"]


def test_trial_summary_corrupt_artifact_counted_never_fatal(tmp_path):
    ev.DEFAULT_EVIDENCE_DIR = tmp_path
    (tmp_path / "bad_20260101_000000.json").write_text("{nope", "utf-8")
    (tmp_path / "walk_forward_20260102_000000.json").write_text(json.dumps(
        {"kind": "walk_forward", "payload": {"verdict": "ROBUST"}}), "utf-8")
    t = ev.trial_summary()
    assert t["unreadable"] == 1
    assert t["attempts"] == 1  # unreadable excluded from the attempt count
    assert t["distinct_questions"] == 1