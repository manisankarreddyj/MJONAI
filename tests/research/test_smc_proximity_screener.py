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
