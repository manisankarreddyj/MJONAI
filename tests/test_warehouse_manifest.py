"""Warehouse drift detection: snapshot + create/orphan/change classification.

Clean-room from qanat's plan.py (MIT — mechanism reimplemented, no code
copied). All tests run against tmp parquet files; the live warehouse is never
touched (manifest path is injectable everywhere it matters).
"""
import json

import pandas as pd
import pytest

from tools.scripts import warehouse_manifest as wm


def _write(root, rel, n_rows=5):
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"a": range(n_rows)}).to_parquet(path, index=False)
    return path


def test_scan_records_rows_bytes_mtime(tmp_path):
    wh = tmp_path / "wh"
    _write(wh, "fno_chain/eod/2024-06.parquet", n_rows=7)
    state = wm._scan(warehouse_root=wh)
    assert state == {"fno_chain/eod/2024-06.parquet": state["fno_chain/eod/2024-06.parquet"]}
    rec = state["fno_chain/eod/2024-06.parquet"]
    assert rec["rows"] == 7 and rec["bytes"] > 0 and rec["mtime"] > 0


def test_scan_empty_root_is_empty(tmp_path):
    assert wm._scan(warehouse_root=tmp_path / "nope") == {}


def test_diff_classifies_create_orphan_change(tmp_path):
    wh = tmp_path / "wh"
    _write(wh, "a/2024-01.parquet", n_rows=5)
    _write(wh, "a/2024-02.parquet", n_rows=5)
    _write(wh, "a/2024-03.parquet", n_rows=5)
    old = wm._scan(warehouse_root=wh)

    # change: rewrite 2024-02 with different rows; orphan: delete 2024-03; create: add 2024-04
    _write(wh, "a/2024-02.parquet", n_rows=9)
    (wh / "a/2024-03.parquet").unlink()
    _write(wh, "a/2024-04.parquet", n_rows=5)
    new = wm._scan(warehouse_root=wh)

    drift = wm.diff_manifests(old, new)
    assert drift["clean"] is False
    assert drift["created"] == ["a/2024-04.parquet"]
    assert drift["orphaned"] == ["a/2024-03.parquet"]
    assert [c["file"] for c in drift["changed"]] == ["a/2024-02.parquet"]
    assert "rows" in drift["changed"][0]["fields"]


def test_diff_clean_on_identical_snapshot(tmp_path):
    wh = tmp_path / "wh"
    _write(wh, "a/2024-01.parquet", n_rows=5)
    assert wm.diff_manifests(wm._scan(warehouse_root=wh),
                             wm._scan(warehouse_root=wh))["clean"] is True


def test_build_then_check_round_trip(tmp_path, monkeypatch, capsys):
    wh = tmp_path / "wh"
    _write(wh, "a/2024-01.parquet", n_rows=5)
    man = tmp_path / "manifest.json"
    monkeypatch.setattr(wm, "WAREHOUSE_ROOT", wh)
    monkeypatch.setattr(wm, "MANIFEST_PATH", man)
    assert wm.main(["--build"]) == 0
    assert man.is_file()
    assert wm.main(["--check"]) == 0
    assert "CLEAN" in capsys.readouterr().out


def test_check_reports_drift_exit_2(tmp_path, monkeypatch, capsys):
    wh = tmp_path / "wh"
    _write(wh, "a/2024-01.parquet", n_rows=5)
    man = tmp_path / "manifest.json"
    monkeypatch.setattr(wm, "WAREHOUSE_ROOT", wh)
    monkeypatch.setattr(wm, "MANIFEST_PATH", man)
    assert wm.main(["--build"]) == 0
    _write(wh, "a/2024-02.parquet", n_rows=5)
    assert wm.main(["--check"]) == 2
    out = capsys.readouterr().out
    assert "DRIFT" in out and "a/2024-02.parquet" in out


def test_check_without_snapshot_fails_closed(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(wm, "WAREHOUSE_ROOT", tmp_path / "wh")
    monkeypatch.setattr(wm, "MANIFEST_PATH", tmp_path / "manifest.json")
    assert wm.main(["--check"]) == 1
    assert "run --build first" in capsys.readouterr().err
