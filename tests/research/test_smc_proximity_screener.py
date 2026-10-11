"""SMC proximity screener contract (clean-room concept screening).

structure_row must be fail-closed (short frames / feature errors -> skipped, never a
fabricated "far from structure" row), the CSV/JSON sinks must round-trip, and
ranking must put honest nulls last.
"""
import json

import pandas as pd
import pytest

from apps.research.run_smc_proximity_screener import rank_rows, structure_row, write_csv, write_json


def _df(n: int = 160) -> pd.DataFrame:
    import numpy as np

    idx = pd.date_range("2025-01-01", periods=n, freq="D")
    # A wave (not a monotone ramp): swing highs/lows actually exist to confirm.
    vals = 100.0 + 10.0 * np.sin(np.arange(n, dtype=float) / 5.0)
    return pd.DataFrame(
        {"Open": vals, "High": vals + 0.5, "Low": vals - 0.5, "Close": vals, "Volume": 1000.0},
        index=idx,
    )


def test_structure_row_reports_distance_and_fvg_state():
    row = structure_row("infy", _df())
    assert row is not None and row["symbol"] == "INFY"
    assert set(row) == {"symbol", "bars", "last_close", "dist_to_swing", "proximity_pct",
                        "fvg_dir", "in_bull_fvg", "in_bear_fvg"}
    # The carried-forward confirmed swing makes the distance computable on a
    # 160-bar frame (the raw feature would be NaN off the confirmation bar).
    assert row["dist_to_swing"] is not None and isinstance(row["dist_to_swing"], float)
    assert row["proximity_pct"] == round(abs(row["dist_to_swing"]) * 100.0, 2)
    assert row["fvg_dir"] in (1, -1, 0)


def test_structure_row_fails_closed_on_short_frame():
    assert structure_row("TCS", _df(n=30)) is None
    assert structure_row("TCS", None) is None


def test_ranking_puts_unknown_distance_last():
    rows = [
        {"symbol": "A", "proximity_pct": 0.8},
        {"symbol": "B", "proximity_pct": None},
        {"symbol": "C", "proximity_pct": 0.1},
    ]
    assert [r["symbol"] for r in rank_rows(rows)] == ["C", "A", "B"]


def test_sinks_round_trip(tmp_path):
    rows = [{"symbol": "A", "last_close": 100.0, "proximity_pct": 0.5}]
    csv_path = write_csv(rows, tmp_path / "p.csv")
    json_path = write_json(rows, tmp_path / "p.json")
    assert "symbol" in csv_path.read_text(encoding="utf-8")
    assert json.loads(json_path.read_text(encoding="utf-8"))["count"] == 1


def test_main_records_evidence_and_writes_sinks(tmp_path, monkeypatch, capsys):
    """The screening run must feed the canonical evidence store, not ad-hoc files."""
    import apps.research.run_smc_proximity_screener as cli

    monkeypatch.setattr(cli, "structure_row", lambda sym, df, swing_length: {
        "symbol": sym, "bars": 160, "last_close": 100.0, "dist_to_swing": -0.05,
        "proximity_pct": 5.0, "fvg_dir": 1, "in_bull_fvg": True, "in_bear_fvg": False})
    import mjonai.data.angelone.historical as hist
    monkeypatch.setattr(hist, "fetch_historical_candles", lambda *a, **k: _df())
    recorded = {}
    monkeypatch.setattr("mjonai.research.evidence.record_evidence",
                        lambda kind, payload: recorded.update(kind=kind, payload=payload) or "path/to/artifact.json")
    monkeypatch.setattr("sys.argv", ["x", "--symbols", "RELIANCE,INFY",
                                     "--out", str(tmp_path / "out")])
    cli.main()
    out = capsys.readouterr().out
    assert recorded["kind"] == "smc_proximity"
    assert [r["symbol"] for r in recorded["payload"]["rows"]] == ["RELIANCE", "INFY"]
    assert (tmp_path / "out" / "proximity.csv").is_file()
    assert "[evidence]" in out
