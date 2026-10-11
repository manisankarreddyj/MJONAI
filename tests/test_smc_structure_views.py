"""SMC structure view contract (web tier).

The web view READS the research-exported snapshot — it never imports the discovery
fence (tests/test_architecture_rules.py enforces that). Fail-closed: a missing or
unreadable snapshot returns available=false with the export hint; a present snapshot
passes through with the disclosure attached.
"""
import json

import pytest

from apps.web import data_views as dv


@pytest.fixture
def snap_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(dv, "_SMC_SNAPSHOT_DIR", tmp_path)
    return tmp_path


def test_absent_snapshot_fails_closed_with_hint(snap_dir):
    out = dv.build_smc_structure("INFY", "1d")
    assert out["available"] is False
    assert "run_smc_structure_export" in out["reason"]
    assert "RISK OVERLAY, NOT ALPHA" in out["disclosure"]
    assert "fvg_zones" not in out          # no fabricated markers


def test_present_snapshot_passes_through_with_disclosure(snap_dir):
    payload = {
        "symbol": "INFY", "timeframe": "1d", "available": True,
        "bars": [{"time": 1700000000, "close": 1500.0}],
        "fvg_zones": [{"time": 1699990000, "low": 1495.0, "high": 1505.0, "dir": 1}],
        "swings": [{"time": 1699980000, "level": 1480.0, "dir": 1}],
        "current": {"smc_fvg_dir": 1, "smc_swing_hl": 1, "in_bull_fvg": True, "in_bear_fvg": False, "dist_to_swing": 0.01},
    }
    (snap_dir / "INFY_1d.json").write_text(json.dumps(payload), encoding="utf-8")
    out = dv.build_smc_structure("infy", "1d")
    assert out["available"] is not False            # truthy payload passed through as-is
    assert out["fvg_zones"] == payload["fvg_zones"]
    assert out["current"]["in_bull_fvg"] is True
    assert out["disclosure"] == payload.get("disclosure") or "RISK OVERLAY" in out["disclosure"]


def test_unreadable_snapshot_fails_closed(snap_dir):
    (snap_dir / "TCS_1d.json").write_text("{not json", encoding="utf-8")
    out = dv.build_smc_structure("TCS", "1d")
    assert out["available"] is False
    assert "unreadable snapshot" in out["reason"]
